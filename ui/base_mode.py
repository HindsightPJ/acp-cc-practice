import tkinter as tk
from tkinter import ttk

from typing import List, Dict, Any, Optional, cast
from abc import ABC, abstractmethod

from quiz_engine import QuizEngine
from models import Question
from app_state import AppState
from data_manager import DataManager
from .theme import Theme, font_ui, font_ui_semibold

theme = Theme()


class BaseMode(ABC, ttk.Frame):
    """练习模式的抽象基类，包含公共功能和生命周期管理。

    TD-30: 引入 AppState 解耦 UI 与状态管理。progress 参数既可以是旧的 dict，
    也可以是 AppState 实例；基类统一包装为状态对象供子类使用。
    """

    def __init__(
        self, parent, questions: List[Question], data_manager, progress: Optional[Any]
    ):
        super().__init__(parent)
        self.questions: List[Question] = questions
        self.data_manager = data_manager
        self._after_jobs: List[Any] = []  # 跟踪所有 after 回调
        self.engine: Optional[QuizEngine] = None  # 基类保证属性存在，子类覆盖
        self.current_index = 0

        if isinstance(progress, AppState):
            self._state = progress
        else:
            self._state = AppState(data_manager, progress)

    @property
    def app_state(self) -> AppState:
        """返回应用状态对象（懒加载，兼容 __new__ 构造的测试对象）。"""
        if not hasattr(self, "_state"):
            self._state = AppState(
                cast(DataManager, getattr(self, "data_manager", None)),
                getattr(self, "progress", {}),
            )
        return self._state

    def _add_after_job(self, job_id) -> None:
        """添加 after 作业并跟踪"""
        self._after_jobs.append(job_id)

    def _cancel_all_after_jobs(self) -> None:
        """取消所有待执行的 after 回调"""
        for job_id in self._after_jobs:
            try:
                self.after_cancel(job_id)
            except tk.TclError:
                pass  # widget 已销毁或 job 已执行
        self._after_jobs.clear()

    def flush_pending_save(self) -> None:
        """销毁前强制保存延迟的进度数据，子类可覆盖。"""
        pass

    def destroy(self) -> None:
        """窗口销毁时清理所有待执行的回调和事件绑定"""
        self.flush_pending_save()
        self._cancel_all_after_jobs()
        try:
            self.unbind("<Key>")
            self.unbind("<Button-1>")
        except tk.TclError:
            pass  # widget 已销毁
        super().destroy()

    def _create_toolbar(self, parent) -> tuple:
        """创建公共工具栏，返回 (toolbar, progress_label, type_label)"""
        toolbar = tk.Frame(parent, bg=theme.BG_PAGE)
        toolbar.pack(fill=tk.X, pady=(0, 12))

        toolbar_left = tk.Frame(toolbar, bg=theme.BG_PAGE)
        toolbar_left.pack(side=tk.LEFT)

        progress_label = tk.Label(
            toolbar_left,
            text="第 0 题 / 共 0 题",
            font=font_ui(11),
            fg=theme.TEXT_SECONDARY,
            bg=theme.BG_PAGE,
        )
        progress_label.pack(side=tk.LEFT, padx=(0, 16))

        type_label = tk.Label(
            toolbar_left,
            text="单选题",
            font=font_ui_semibold(10),
            fg=theme.ACCENT,
            bg=theme.BG_PAGE,
        )
        type_label.pack(side=tk.LEFT)

        return toolbar, progress_label, type_label

    def _create_progress_bar(self, parent) -> tuple:
        """创建进度条，返回 (progress_bg, progress_bar_fill)"""
        progress_bg = tk.Frame(parent, bg=theme.BORDER, height=3)
        progress_bg.pack(fill=tk.X, pady=(0, 16))
        progress_bg.pack_propagate(False)

        progress_bar_fill = tk.Frame(progress_bg, bg=theme.ACCENT, width=0, height=3)
        progress_bar_fill.place(x=0, y=0, relheight=1.0)

        return progress_bg, progress_bar_fill

    def _update_progress_bar_width(
        self, progress_bar_fill, container_width: int, percentage: float
    ) -> None:
        """更新进度条宽度"""
        if container_width > 0:
            bar_width = int(container_width * (percentage / 100))
            progress_bar_fill.configure(width=max(bar_width, 0))

    def _bind_keyboard(self) -> None:
        """绑定键盘事件"""
        self.focus_set()
        self.bind("<Key>", self._on_key_press)
        self.bind("<Button-1>", self._on_global_click)

    def _on_global_click(self, event) -> None:
        """全局点击处理，设置焦点。

        切 tab 时旧 mode 被 destroy，但 bind_all 注册的全局 callback 仍在
        Tcl 绑定表里，下次点击会调用已销毁 widget 的 focus_set 抛 TclError，
        静默忽略即可——旧 mode 已不活动，无需 focus。
        """
        try:
            self.focus_set()
        except tk.TclError:
            pass

    def _handle_option_key_press(
        self, event, on_select, on_submit, is_answered_check
    ) -> Optional[str]:
        """通用的选项选择键盘处理 - 处理 A-F、1-6、Enter 按键。
        
        Args:
            event: 键盘事件
            on_select: 选择选项的回调函数，接受 letter 参数
            on_submit: 提交答案的回调函数
            is_answered_check: 检查是否已答题的函数
        
        Returns:
            "break" 如果处理了事件，否则 None
        """
        if not self.engine or not self.engine.get_current_question():
            return None
        
        key = event.char.upper() if event.char else ""
        keysym = event.keysym
        
        question = self.engine.get_current_question()
        if question is None:
            return None

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

    def _on_key_press(self, event):
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

    def next_question(self) -> Optional[Dict[str, Any]]:
        """下一题"""
        if self.engine and self.engine.has_next():
            self.engine.next_question()
            self.current_index = self.engine.get_current_index()  # TD-15: 显式接口
            return self.engine.get_current_question()
        return None

    def prev_question(self) -> Optional[Dict[str, Any]]:
        """上一题"""
        if self.engine and self.engine.has_prev():
            self.engine.prev_question()
            self.current_index = self.engine.get_current_index()  # TD-15: 显式接口
            return self.engine.get_current_question()
        return None

    # 抽象方法 - 子类必须实现
    @abstractmethod
    def _setup_mode_ui(self) -> None:
        """模式特有的UI初始化"""
        pass
