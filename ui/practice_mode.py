import tkinter as tk
from tkinter import messagebox
from typing import Any, Optional

from .theme import Theme, font_ui, create_normal_button

from quiz_engine import QuizEngine
from models import Question
from data_manager import DataManager
from .base_mode import BaseMode
from .practice_session import PracticeSession
from .practice_panel import PracticePanel

theme = Theme()


class PracticeMode(BaseMode):
    def __init__(
        self,
        parent,
        questions: list[Question],
        data_manager: Optional[DataManager],
        progress: Optional[Any],
    ) -> None:
        super().__init__(parent, questions, data_manager, progress)
        self.engine: QuizEngine = QuizEngine(questions)
        self._pending_save = False

        # 使用 PracticeSession 管理练习逻辑
        self.session = PracticeSession(self.engine, self.app_state)

        self._setup_mode_ui()
        self.start_new_session()
        self._bind_keyboard()

    def _setup_mode_ui(self):
        """构建练习模式 UI。"""
        self.configure(style="TFrame")

        # 顶部工具栏（含随机出题、重新开始）
        toolbar = tk.Frame(self, bg=theme.BG_PAGE)
        toolbar.pack(fill=tk.X, pady=(0, 12))

        toolbar_left = tk.Frame(toolbar, bg=theme.BG_PAGE)
        toolbar_left.pack(side=tk.LEFT)

        toolbar_right = tk.Frame(toolbar, bg=theme.BG_PAGE)
        toolbar_right.pack(side=tk.RIGHT)

        self.shuffle_var = tk.BooleanVar(value=False)
        shuffle_check = tk.Checkbutton(
            toolbar_right,
            text="随机出题",
            variable=self.shuffle_var,
            command=self.restart_session,
            font=font_ui(10),
            fg=theme.TEXT_SECONDARY,
            bg=theme.BG_PAGE,
            selectcolor=theme.BG_CARD,
            activebackground=theme.BG_PAGE,
            activeforeground=theme.ACCENT,
            cursor="hand2",
        )
        shuffle_check.pack(side=tk.LEFT, padx=(0, 8))

        restart_btn = create_normal_button(
            toolbar_right,
            text="重新开始",
            command=self.restart_session,
            padx=12,
            pady=4,
        )
        restart_btn.pack(side=tk.LEFT)

        # 使用统一的 PracticePanel 渲染练习视图
        self.panel = PracticePanel(
            self,
            session=self.session,
            on_finish=lambda: messagebox.showinfo("提示", "已完成所有题目！"),
        )
        self.panel.pack(fill=tk.BOTH, expand=True)

    def _on_key_press(self, event):
        # 先尝试通用的选项键盘处理
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

    def start_new_session(self) -> None:
        if self.engine is None:
            return
        shuffle = self.shuffle_var.get()
        self.panel.reset_session(shuffle=shuffle)

    def restart_session(self) -> None:
        self.start_new_session()

    def load_current_question(self) -> None:
        """保留方法名以便外部调用，实际由 PracticePanel 负责渲染。"""
        self.panel.load_current_question()

    def submit_answer(self) -> None:
        """保留方法名以便外部调用，实际由 PracticePanel 负责提交。"""
        self.panel.submit_answer()
        self._save_progress_delayed()

    def next_question(self) -> None:
        self.panel.next_question()

    def prev_question(self) -> None:
        self.panel.prev_question()

    def _save_progress_delayed(self):
        self._cancel_all_after_jobs()
        self._pending_save = True
        job_id = self.after(2000, self._do_save_progress)
        self._add_after_job(job_id)

    def _do_save_progress(self):
        self._pending_save = False
        self.app_state.save()

    def flush_pending_save(self) -> None:
        """切 tab 前强制保存延迟的进度，避免数据丢失。"""
        if self._pending_save:
            self._cancel_all_after_jobs()
            self._pending_save = False
            self.app_state.save_safe()
