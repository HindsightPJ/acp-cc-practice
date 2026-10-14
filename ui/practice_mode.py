import tkinter as tk
from tkinter import messagebox
from .theme import theme, font_ui, create_normal_button, create_switch

from quiz_engine import QuizEngine
from models import Question
from data_manager import DataManager
from app_state import AppState
from .base_mode import BaseMode
from .practice_session import PracticeSession
from .practice_panel import PracticePanel
from .mode_toolbar import ModeToolbar


class PracticeMode(BaseMode):
    # P2-9: 覆盖基类的保存失败提示文案
    _save_failure_message = "学习进度保存失败，请检查磁盘空间或文件权限。"

    def __init__(
        self,
        parent: tk.Misc,
        questions: list[Question],
        data_manager: DataManager | None,
        progress: AppState,
    ) -> None:
        super().__init__(parent, questions, data_manager, progress)
        self.engine: QuizEngine = QuizEngine(questions)

        # 使用 PracticeSession 管理练习逻辑
        self.session = PracticeSession(self.engine, self.app_state)
        # 已实际生效的 shuffle 状态（取消"重新开始"时用于回滚复选框显示）
        self._applied_shuffle = False

        self._setup_mode_ui()
        self._restore_or_start_session()
        self._bind_keyboard()

    def _setup_mode_ui(self) -> None:
        """构建练习模式 UI。"""
        self.configure(style="TFrame")

        # 顶部工具栏（含随机出题、重新开始）
        toolbar = ModeToolbar(self)

        self.shuffle_var = tk.BooleanVar(value=False)
        create_switch(toolbar.right, self.shuffle_var, self.start_new_session).pack(side=tk.LEFT)
        tk.Label(
            toolbar.right,
            text="随机出题",
            font=font_ui(11),
            fg=theme.TEXT_SECONDARY,
            bg=theme.BG_PAGE,
        ).pack(side=tk.LEFT, padx=(6, 16))

        restart_btn = create_normal_button(
            toolbar.right,
            text="重新开始",
            command=self.start_new_session,
            padx=12,
            pady=4,
        )
        restart_btn.pack(side=tk.LEFT)

        # 使用统一的 PracticePanel 渲染练习视图。
        # P0 修复：on_submit/on_navigate 必须接线，否则防抖保存永不触发
        # （练习统计与错题入库只在内存，关应用即丢）。
        self.panel = PracticePanel(
            self,
            session=self.session,
            on_finish=self._on_practice_finished,
            on_submit=self._on_answer_submitted,
            on_navigate=self._on_navigated,
        )
        self.panel.pack(fill=tk.BOTH, expand=True)

    # ------------------------------------------------------------------
    # 提交 / 导航 / 完成钩子（两条提交路径在此单点汇合）
    # ------------------------------------------------------------------

    def _on_answer_submitted(self) -> None:
        """提交完成后钩子（由 PracticePanel.on_submit 触发）。

        只做"提交完成后"的动作：焦点回收 + 防抖保存。提交动作本身由
        panel 完成——本方法不得再调用 panel.submit_answer（无限递归）。
        """
        # P2-UX: 焦点回到模式容器，使方向键导航继续生效
        self.focus_set()
        self._save_progress_delayed()

    def _on_navigated(self) -> None:
        """切题后钩子：位置变化也纳入防抖持久化（进度恢复用）。"""
        self._save_progress_delayed()

    def _on_practice_finished(self) -> None:
        """队列完成：快照保持在末题状态，提示完成（替代原 on_finish 元组 lambda）。"""
        self._save_progress_delayed()
        messagebox.showinfo("提示", "已完成所有题目！", parent=self)

    def _save_progress_delayed(self) -> None:
        """先同步练习会话快照，再走基类防抖落盘（快照唯一写入口）。

        提交 / 导航 / 重新开始 / 完成四个时机统一经此方法，快照与内存
        状态不会漂移；考试历史等无关数据不受影响。
        """
        self.app_state.set_practice_progress(self.session.export_state())
        super()._save_progress_delayed()

    # ------------------------------------------------------------------
    # 会话生命周期
    # ------------------------------------------------------------------

    def _restore_or_start_session(self) -> None:
        """启动时尝试恢复上次练习（进度恢复）；快照无效则全新开始。"""
        state = self.app_state.get_practice_progress()
        if state and self.session.restore_state(state):
            self._applied_shuffle = bool(state.get("shuffle", False))
            self.shuffle_var.set(self._applied_shuffle)
            self.panel.load_current_question()
        else:
            self.panel.reset_session(shuffle=False)

    def start_new_session(self) -> None:
        if self.engine is None:
            return
        new_shuffle = self.shuffle_var.get()
        # P3 修复：已有作答时先确认，避免静默清空当前进度
        if self.engine.has_answers() and not messagebox.askyesno(
            "重新开始",
            "当前作答记录将被清空，确定重新开始吗？",
            parent=self,
        ):
            # 取消：回滚复选框到实际生效的状态（command 触发前 Tk 已翻转它）
            self.shuffle_var.set(self._applied_shuffle)
            return
        self._applied_shuffle = new_shuffle
        self.panel.reset_session(shuffle=new_shuffle)
        self._save_progress_delayed()

    # ------------------------------------------------------------------
    # 键盘与兼容入口
    # ------------------------------------------------------------------

    def _on_key_press(self, event: tk.Event) -> str | None:
        # 先尝试通用的选项键盘处理（提交直通 panel，完成后 panel 触发钩子）
        result = self._handle_option_key_press(
            event,
            on_select=self.panel.handle_option_click,
            on_submit=self.panel.submit_answer,
            is_answered_check=lambda: self.session.is_answered,
        )
        if result == "break":
            return "break"

        # 导航键交给面板处理
        panel_result = self.panel.handle_key_press(event)
        if panel_result == "break":
            return "break"

        return super()._on_key_press(event)

    def submit_answer(self) -> None:
        """委托 panel 提交（保留方法名供测试与外部调用）。

        生产路径不经过本方法：按钮/键盘均直达 panel.submit_answer，
        提交完成后由 panel 统一触发 _on_answer_submitted 钩子完成
        焦点回收与防抖保存。
        """
        self.panel.submit_answer()
