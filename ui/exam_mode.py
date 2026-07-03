import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import List, Dict, Any, Optional

from .theme import Theme, font_ui, font_ui_semibold, create_primary_button, create_card

from quiz_engine import QuizEngine
from models import Question
from data_manager import DataManager
from .base_mode import BaseMode
from .exam_panel import ExamPanel
from .exam_report_dialog import ExamReportDialog
from .exam_session import ExamSession

theme = Theme()


class ExamMode(BaseMode):
    """考试模式编排层。

    P0-2: 视图渲染委托给 ExamPanel，本类只负责：
    设置卡片、启动考试、计时循环、交卷评分、历史保存、报告展示。
    """

    def __init__(
        self,
        parent,
        questions: List[Question],
        data_manager: Optional[DataManager],
        progress: Optional[Any],
    ) -> None:
        super().__init__(parent, questions, data_manager, progress)
        self.engine: Optional[QuizEngine] = None
        self.timer_running = False
        self.time_remaining = 0
        self.exam_total_seconds = 0
        self.exam_session: Optional[ExamSession] = None
        self.panel: Optional[ExamPanel] = None

        self._setup_mode_ui()
        self._bind_keyboard()

    def _on_key_press(self, event):
        """键盘事件委托给 ExamPanel（考试进行中）。

        考试未开始时 panel 为 None，不处理按键。
        """
        if self.panel is not None:
            return self.panel.handle_key_press(event)
        return None

    # ------------------------------------------------------------------
    # 设置卡片 UI
    # ------------------------------------------------------------------

    def _setup_mode_ui(self):
        self.configure(style="TFrame")

        settings_card, s_inner = create_card(self, inner_padx=24, inner_pady=20)
        settings_card.pack(fill=tk.X, pady=(0, 16))

        s_title = tk.Label(
            s_inner,
            text="模拟考试",
            font=font_ui_semibold(14),
            fg=theme.TEXT_PRIMARY,
            bg=theme.BG_CARD,
        )
        s_title.pack(anchor=tk.W, pady=(0, 16))

        settings_row = tk.Frame(s_inner, bg=theme.BG_CARD)
        settings_row.pack(fill=tk.X)

        q_frame = tk.Frame(settings_row, bg=theme.BG_CARD)
        q_frame.pack(side=tk.LEFT, padx=(0, 32))

        q_label = tk.Label(
            q_frame, text="题目数量", font=font_ui(11), fg=theme.TEXT_SECONDARY, bg=theme.BG_CARD
        )
        q_label.pack(side=tk.LEFT, padx=(0, 10))

        self.question_count_var = tk.StringVar(value="100")
        count_combo = ttk.Combobox(
            q_frame,
            textvariable=self.question_count_var,
            values=["50", "100", "150", "200"],
            width=8,
            state="readonly",
            font=font_ui(10),
        )
        count_combo.pack(side=tk.LEFT)

        d_frame = tk.Frame(settings_row, bg=theme.BG_CARD)
        d_frame.pack(side=tk.LEFT, padx=(0, 32))

        d_label = tk.Label(
            d_frame,
            text="考试时长(分钟)",
            font=font_ui(11),
            fg=theme.TEXT_SECONDARY,
            bg=theme.BG_CARD,
        )
        d_label.pack(side=tk.LEFT, padx=(0, 10))

        self.duration_var = tk.StringVar(value="60")
        duration_combo = ttk.Combobox(
            d_frame,
            textvariable=self.duration_var,
            values=["30", "60", "90", "120"],
            width=8,
            state="readonly",
            font=font_ui(10),
        )
        duration_combo.pack(side=tk.LEFT)

        self.start_btn = create_primary_button(
            settings_row,
            text="开始考试",
            command=self.start_exam,
            padx=24,
        )
        self.start_btn.pack(side=tk.RIGHT)

        # 考试容器：承载 ExamPanel
        self.exam_container = tk.Frame(self, bg=theme.BG_PAGE)

    # ------------------------------------------------------------------
    # 考试编排
    # ------------------------------------------------------------------

    def start_exam(self) -> None:
        self._cancel_all_after_jobs()
        try:
            question_count = int(self.question_count_var.get())
            duration = int(self.duration_var.get())
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数值！")
            return

        self.engine = QuizEngine(self.questions)
        self.engine.start_exam_mode(question_count=question_count)
        self.exam_session = ExamSession(self.engine)

        self.exam_total_seconds = duration * 60
        self.time_remaining = self.exam_total_seconds
        self.timer_running = True

        self.start_btn.configure(state=tk.DISABLED, bg=theme.BTN_DISABLED)

        # 创建 ExamPanel 并通过回调连接编排逻辑
        self.panel = ExamPanel(
            self.exam_container,
            engine=self.engine,
            exam_session=self.exam_session,
            on_prev=self.exam_prev_question,
            on_next=self.exam_next_question,
            on_submit=self.submit_exam,
            on_mark=self.toggle_mark_current,
            on_jump=self.jump_to_question,
            on_select_option=self.exam_select_option_by_letter,
        )
        self.panel.pack(fill=tk.BOTH, expand=True)
        self.exam_container.pack(fill=tk.BOTH, expand=True, padx=0, pady=5)

        self.panel.build_nav_buttons(self.engine.queue_length())
        self.panel.load_question()
        self.update_timer()

    def update_timer(self) -> None:
        if not self.timer_running:
            return

        # 用 engine 显式接口计算实际经过时间，避免 after(1000) 累积漂移
        if self.engine:
            elapsed = self.engine.get_exam_elapsed_seconds()
            if elapsed is not None:
                self.time_remaining = max(0, self.exam_total_seconds - elapsed)

        if self.time_remaining <= 0:
            self.timer_running = False
            messagebox.showwarning("时间到", "考试时间已到，将自动交卷！")
            self.submit_exam(force=True)
            return

        if self.panel is not None:
            self.panel.update_timer_display(self.time_remaining, self.exam_total_seconds)

        job_id = self.after(1000, self.update_timer)
        self._add_after_job(job_id)

    def load_exam_question(self) -> None:
        if self.panel is None:
            return
        self.panel.load_question()

    def exam_select_option_by_letter(self, letter: str) -> None:
        """选项选择编排：更新 session 状态 + 同步 panel 视图。"""
        if self.engine is None or self.exam_session is None or self.panel is None:
            return

        selected = self.exam_session.select_option(letter)
        if selected is None:
            return

        self.panel.sync_option_selection(selected)

    def exam_next_question(self) -> None:
        if self.engine is None:
            return
        if self.engine.has_next():
            self.engine.next_question()
            self.load_exam_question()
        else:
            messagebox.showinfo("提示", "已经是最后一题了！")

    def exam_prev_question(self) -> None:
        if self.engine is None:
            return
        if self.engine.has_prev():
            self.engine.prev_question()
            self.load_exam_question()
        else:
            messagebox.showinfo("提示", "已经是第一题了！")

    def jump_to_question(self, idx: int) -> None:
        if self.engine is None:
            return
        if 0 <= idx < self.engine.queue_length():
            self.engine.set_current_index(idx)
            self.load_exam_question()

    def toggle_mark_current(self) -> None:
        if self.engine is None or self.exam_session is None or self.panel is None:
            return
        self.exam_session.toggle_mark()
        self.panel.update_nav_buttons()

    # ------------------------------------------------------------------
    # 交卷与报告
    # ------------------------------------------------------------------

    def submit_exam(self, force: bool = False) -> None:
        if not force and not messagebox.askyesno(
            "确认交卷", "确定要交卷吗？\n\n提交后将无法修改答案。"
        ):
            return

        self._cancel_all_after_jobs()
        self.timer_running = False

        if self.engine is None or self.exam_session is None:
            return

        self.exam_session.record_all_answers()

        report = self.engine.get_exam_report()

        if report:
            self._save_exam_history(report)
            self.show_exam_report(report)

    def _save_exam_history(self, report: Dict[str, Any]) -> None:
        self.app_state.add_exam_history(
            {
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "total_questions": report["total_questions"],
                "correct": report["correct"],
                "wrong": report["wrong"],
                "accuracy": report["accuracy"],
                "time_used": report["time_used"],
            }
        )
        self.app_state.save()

    def show_exam_report(self, report: Dict[str, Any]) -> None:
        """显示考试成绩报告对话框。"""
        dialog = ExamReportDialog(self, report, on_add_wrong=self.add_wrong_to_book)
        dialog.show()

    def add_wrong_to_book(self, report: Dict[str, Any]) -> None:
        added = 0
        for q in report["wrong_questions"]:
            q_num = q.number
            if not self.app_state.is_wrong_question(q_num):
                self.app_state.add_wrong_question(q_num)
                added += 1

        self.app_state.save()
        messagebox.showinfo("成功", f"已将 {added} 道错题加入错题本！")
