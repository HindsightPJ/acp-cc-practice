import tkinter as tk
from tkinter import ttk, messagebox

from typing import Callable
from abc import ABC, abstractmethod

from quiz_engine import QuizEngine
from models import Question
from app_state import AppState
from data_manager import DataManager


class BaseMode(ABC, ttk.Frame):
    """练习模式的抽象基类，包含公共功能和生命周期管理。

    TD-30: 引入 AppState 解耦 UI 与状态管理。

    P2-9: 防抖保存三件套（_save_progress_delayed/_do_save_progress/flush_pending_save）
    统一在基类实现，子类通过覆盖 _save_failure_message 定制文案。
    """

    # P2-9: 子类可覆盖此属性定制保存失败提示文案
    _save_failure_message: str = "进度保存失败，请检查磁盘空间或文件权限。"

    def __init__(
        self,
        parent: tk.Misc,
        questions: list[Question],
        data_manager: DataManager | None,
        progress: AppState,
    ) -> None:
        super().__init__(parent)
        self.questions: list[Question] = questions
        self.data_manager = data_manager
        # P2-TIMER: 保存任务单独跟踪，避免 _save_progress_delayed 误取消计时器、
        # 自动显示答案等其他职责的 after 任务
        self._after_jobs: list[str] = []  # 非保存类 after 任务
        self._save_job_id: str | None = None  # 防抖保存任务
        self.engine: QuizEngine | None = None  # 基类保证属性存在，子类覆盖
        # P2-9: 防抖保存标记，统一在基类管理
        self._pending_save: bool = False

        self._state = progress

    @property
    def app_state(self) -> AppState:
        """返回应用状态对象。"""
        return self._state

    def _add_after_job(self, job_id: str) -> None:
        """添加非保存类 after 作业并跟踪"""
        self._after_jobs.append(job_id)

    def _cancel_all_after_jobs(self) -> None:
        """取消所有待执行的非保存类 after 回调（保存任务单独管理）。"""
        for job_id in self._after_jobs:
            try:
                self.after_cancel(job_id)
            except tk.TclError:
                pass  # widget 已销毁或 job 已执行
        self._after_jobs.clear()
        # 保存任务也一并清理，确保 destroy/start_exam 等场景彻底取消
        self._cancel_save_job()

    def _cancel_save_job(self) -> None:
        """取消待执行的防抖保存任务。"""
        if self._save_job_id is not None:
            try:
                self.after_cancel(self._save_job_id)
            except tk.TclError:
                pass  # widget 已销毁或 job 已执行
            self._save_job_id = None

    # ------------------------------------------------------------------
    # 防抖保存（P2-9: 从 PracticeMode/ReviewMode 提取的公共逻辑）
    # ------------------------------------------------------------------

    def _save_progress_delayed(self) -> None:
        """标记有待保存的进度，2 秒后落盘（期间新的调用会重置计时器）。"""
        # P2-TIMER: 只取消保存任务，不碰计时器、自动显示答案等其他任务
        self._cancel_save_job()
        self._pending_save = True
        self._save_job_id = self.after(2000, self._do_save_progress)

    def _do_save_progress(self) -> None:
        """延迟计时器到期时执行实际保存。"""
        self._save_job_id = None
        # P2-16: 先保存成功再重置 _pending_save，避免保存失败时
        # 标记被清空导致后续无法重试（数据丢失风险）
        if self.app_state.save_safe():
            self._pending_save = False
        else:
            messagebox.showwarning(
                "保存失败",
                self._save_failure_message,
                parent=self,
            )

    def flush_pending_save(self) -> None:
        """切 tab / 销毁前强制保存延迟的进度，避免数据丢失。

        基类 BaseMode.destroy() 会调用此方法，无需子类显式调用。
        """
        if self._pending_save:
            self._cancel_save_job()
            if self.app_state.save_safe():
                self._pending_save = False
            else:
                messagebox.showwarning(
                    "保存失败",
                    f"{self._save_failure_message}\n\n本次进度可能未落盘。",
                    parent=self,
                )

    def destroy(self) -> None:
        """窗口销毁时清理所有待执行的回调和事件绑定"""
        self.flush_pending_save()
        # P2: flush_pending_save 已取消保存任务；非保存类 after 任务由 Tk 在
        # super().destroy() 时自动清理，无需重复调用 _cancel_all_after_jobs。
        try:
            self.unbind("<Key>")
            self.unbind("<Button-1>")
        except tk.TclError:
            pass  # widget 已销毁
        super().destroy()

    def _bind_keyboard(self) -> None:
        """绑定键盘事件"""
        self.focus_set()
        self.bind("<Key>", self._on_key_press)
        self.bind("<Button-1>", self._on_global_click)

    def _on_global_click(self, event: tk.Event) -> None:
        """点击模式空白区域时设置焦点到模式容器。

        仅当点击目标是模式容器本身（而非子控件）时才抢焦点，避免用户
        点击跳转输入框、按钮等子控件时被父容器夺走焦点。
        """
        if event.widget is not self:
            return
        try:
            self.focus_set()
        except tk.TclError:
            pass

    def _is_input_focused(self) -> bool:
        """判断当前焦点是否在文本输入控件上。

        用于全局键盘快捷键：输入框获得焦点时应跳过选项选择、空格显示答案等
        全局快捷键，让输入控件正常响应按键。
        """
        try:
            focused = self.focus_get()
        except tk.TclError:
            return False
        return isinstance(focused, (tk.Entry, tk.Text, ttk.Entry, ttk.Combobox))

    def _handle_option_key_press(
        self,
        event: tk.Event,
        on_select: Callable[[str], None],
        on_submit: Callable[[], None],
        is_answered_check: Callable[[], bool],
        engine: QuizEngine | None = None,
    ) -> str | None:
        """通用的选项选择键盘处理 - 处理 A-F、1-6、Enter 按键。

        Args:
            event: 键盘事件
            on_select: 选择选项的回调函数，接受 letter 参数
            on_submit: 提交答案的回调函数
            is_answered_check: 检查是否已答题的函数
            engine: 可选的 QuizEngine 实例；未提供时使用 self.engine

        Returns:
            "break" 如果处理了事件，否则 None
        """
        if self._is_input_focused():
            return None

        active_engine = engine or self.engine
        # P2-8: 入口仅调用一次 get_current_question()，避免重复调用
        question = active_engine.get_current_question() if active_engine else None
        if question is None:
            return None

        key = event.char.upper() if event.char else ""
        keysym = event.keysym

        # 字母选择 (A-F)
        if key and key in "ABCDEF" and not is_answered_check():
            card_idx = ord(key) - ord("A")
            options_count = len(question.options)
            if card_idx < options_count:
                on_select(key)
            return "break"

        # 数字选择 (1-6)
        if key and key in "123456" and not is_answered_check():
            card_idx = int(key) - 1
            options_count = len(question.options)
            if card_idx < options_count:
                letter = chr(ord("A") + card_idx)
                on_select(letter)
            return "break"

        # Enter 提交
        if keysym == "Return" and not is_answered_check():
            on_submit()
            return "break"

        return None

    def _on_key_press(self, event: tk.Event) -> str | None:
        """键盘事件处理 - 子类可覆盖。

        导航键（Left/Right）的默认实现映射到 prev_question/next_question。
        子类如有特有按键，可在处理完后 `return super()._on_key_press(event)`
        复用本方法的导航逻辑，避免重复代码（TD-06 修复）。
        """
        keysym = event.keysym

        # 导航键默认处理
        if keysym == "Left":
            self.prev_question()
            return "break"
        if keysym == "Right":
            self.next_question()
            return "break"
        return None

    def next_question(self) -> Question | None:
        """下一题"""
        if self.engine and self.engine.has_next():
            self.engine.next_question()
            return self.engine.get_current_question()
        return None

    def prev_question(self) -> Question | None:
        """上一题"""
        if self.engine and self.engine.has_prev():
            self.engine.prev_question()
            return self.engine.get_current_question()
        return None

    # 抽象方法 - 子类必须实现
    @abstractmethod
    def _setup_mode_ui(self) -> None:
        """模式特有的UI初始化"""
        pass
