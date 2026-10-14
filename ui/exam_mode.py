import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import Any

from .theme import theme, font_ui, font_ui_semibold, create_primary_button, create_card

from quiz_engine import QuizEngine
from models import Question
from data_manager import DataManager
from app_state import AppState
from .base_mode import BaseMode
from .exam_panel import ExamPanel
from .exam_report_dialog import ExamReportDialog
from .exam_session import ExamSession
from .constants import TIMER_TICK_MS


class ExamMode(BaseMode):
    """考试模式编排层。

    P0-2: 视图渲染委托给 ExamPanel，本类只负责：
    设置卡片、启动考试、计时循环、交卷评分、历史保存、报告展示。
    """

    def __init__(
        self,
        parent: tk.Misc,
        questions: list[Question],
        data_manager: DataManager | None,
        progress: AppState,
    ) -> None:
        super().__init__(parent, questions, data_manager, progress)
        self.engine: QuizEngine | None = None
        self.timer_running = False
        self.time_remaining = 0
        self.exam_total_seconds = 0
        self.exam_session: ExamSession | None = None
        self.panel: ExamPanel | None = None
        # P1-4: 跟踪当前待执行的 timer job，避免 _after_jobs 列表无限增长
        self._timer_job_id: str | None = None

        self._setup_mode_ui()
        self._bind_keyboard()

    def _on_key_press(self, event: tk.Event) -> str | None:
        """键盘分发协议：选项选择走基类统一方法，导航/标记委托 panel。

        考试模式语义：可改答案（is_answered_check 恒 False），Enter 无提交
        语义（交卷仅通过按钮触发，避免误交卷）。
        """
        if self._is_input_focused():
            return None
        if self.engine is None or not self.engine.get_current_question():
            return None
        if self.panel is None:
            return None

        # 选项选择：复用基类 _handle_option_key_press，与 PracticeMode/WrongBook 统一
        result = self._handle_option_key_press(
            event,
            on_select=self.exam_select_option_by_letter,
            on_submit=lambda: None,
            is_answered_check=lambda: False,
        )
        if result == "break":
            return "break"

        # 导航与标记：委托 panel
        return self.panel.handle_key_press(event)

    # ------------------------------------------------------------------
    # 设置卡片 UI
    # ------------------------------------------------------------------

    def _setup_mode_ui(self) -> None:
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

        # P0-6: 考试历史卡片——展示最近 20 条考试记录（日期/题数/正确/错误/正确率/用时）
        self._setup_history_card()

        # 考试容器：承载 ExamPanel
        self.exam_container = tk.Frame(self, bg=theme.BG_PAGE)

    # ------------------------------------------------------------------
    # 考试历史卡片（P0-6）
    # ------------------------------------------------------------------

    def _setup_history_card(self) -> None:
        """构建考试历史卡片，展示最近 20 条考试记录。"""
        history_card, h_inner = create_card(self, inner_padx=20, inner_pady=16)
        history_card.pack(fill=tk.X, pady=(0, 16))

        header = tk.Frame(h_inner, bg=theme.BG_CARD)
        header.pack(fill=tk.X, pady=(0, 10))

        h_title = tk.Label(
            header,
            text="最近考试历史",
            font=font_ui_semibold(13),
            fg=theme.TEXT_PRIMARY,
            bg=theme.BG_CARD,
        )
        h_title.pack(side=tk.LEFT)

        self.history_count_label = tk.Label(
            header,
            text="",
            font=font_ui(10),
            fg=theme.TEXT_MUTED,
            bg=theme.BG_CARD,
        )
        self.history_count_label.pack(side=tk.LEFT, padx=(8, 0))

        # 空状态提示（无历史时显示）
        self.history_empty_label = tk.Label(
            h_inner,
            text="暂无考试记录，开始一场模拟考试后将在此显示成绩。",
            font=font_ui(11),
            fg=theme.TEXT_MUTED,
            bg=theme.BG_CARD,
        )
        self.history_empty_label.pack(fill=tk.X, pady=(8, 0))

        # Treeview 表格（带滚动条）
        tree_frame = tk.Frame(h_inner, bg=theme.BG_CARD)
        self._history_tree_frame = tree_frame

        columns = ("date", "total", "correct", "wrong", "accuracy", "time")
        self.history_tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            height=6,
            selectmode="browse",
        )

        # 列标题与宽度（anchor 必须用字符串字面量以满足 mypy Literal 类型要求）
        self.history_tree.heading("date", text="日期")
        self.history_tree.column("date", width=130, anchor="w", stretch=False)
        self.history_tree.heading("total", text="题数")
        self.history_tree.column("total", width=60, anchor="center", stretch=False)
        self.history_tree.heading("correct", text="正确")
        self.history_tree.column("correct", width=60, anchor="center", stretch=False)
        self.history_tree.heading("wrong", text="错误")
        self.history_tree.column("wrong", width=60, anchor="center", stretch=False)
        self.history_tree.heading("accuracy", text="正确率")
        self.history_tree.column("accuracy", width=80, anchor="center", stretch=False)
        self.history_tree.heading("time", text="用时")
        self.history_tree.column("time", width=100, anchor="center", stretch=False)

        # 行样式：交替背景色提升可读性
        self.history_tree.tag_configure("odd", background=theme.BG_CARD)
        self.history_tree.tag_configure("even", background=theme.BG_HOVER)

        # 滚动条
        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=vsb.set)

        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # 初始刷新一次（如果有历史则显示 Treeview，否则只显示空状态提示）
        self._refresh_history_view()

    def _refresh_history_view(self) -> None:
        """根据当前 app_state 中的考试历史刷新表格。"""
        if not hasattr(self, "history_tree"):
            return

        # 清空旧行
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)

        history = self.app_state.get_exam_history()
        # 最新记录在最上方（get_exam_history 按时间正序，倒序展示更直观）
        history_reversed = list(reversed(history))

        count = len(history_reversed)
        if count == 0:
            self.history_count_label.configure(text="")
            self.history_empty_label.pack(fill=tk.X, pady=(8, 0))
            self._history_tree_frame.pack_forget()
            return

        # 有数据：隐藏空状态提示，显示表格
        self.history_empty_label.pack_forget()
        self.history_count_label.configure(text=f"共 {count} 条记录（最多保留 20 条）")
        if not self._history_tree_frame.winfo_ismapped():
            self._history_tree_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        for idx, entry in enumerate(history_reversed):
            tag = "even" if idx % 2 == 0 else "odd"
            # accuracy 保留 1 位小数
            acc = entry.get("accuracy", 0)
            try:
                acc_text = f"{float(acc):.1f}%"
            except (TypeError, ValueError):
                acc_text = "—"
            self.history_tree.insert(
                "",
                tk.END,
                values=(
                    entry.get("date", "—"),
                    entry.get("total_questions", "—"),
                    entry.get("correct", "—"),
                    entry.get("wrong", "—"),
                    acc_text,
                    entry.get("time_used", "—"),
                ),
                tags=(tag,),
            )

    # ------------------------------------------------------------------
    # 考试编排
    # ------------------------------------------------------------------

    def start_exam(self) -> None:
        self._cancel_all_after_jobs()
        # P2-2: 销毁旧 panel，避免重复开考时 widget 泄漏（旧 ExamPanel 及其
        # OptionRow/nav_buttons 未 destroy 会累积内存与悬挂 after 回调）
        if self.panel is not None:
            self.panel.destroy()
            self.panel = None
        try:
            question_count = int(self.question_count_var.get())
            duration = int(self.duration_var.get())
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数值！", parent=self)
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
            messagebox.showwarning("时间到", "考试时间已到，将自动交卷！", parent=self)
            self.submit_exam(force=True)
            return

        if self.panel is not None:
            self.panel.update_timer_display(self.time_remaining, self.exam_total_seconds)

        # P1-4 + P0-5: 周期性 timer 只保留最新的待执行 job，避免 _after_jobs
        # 集合在长时间考试中无限增长（60 分钟 = 3600 个无效引用）。
        # _cancel_after_job 统一 cancel+remove 语义，旧 job 已执行则 after_cancel
        # 抛 TclError 被吞，仅从集合移除；新 job 加入集合并更新引用。
        self._cancel_after_job(self._timer_job_id)
        self._timer_job_id = self.after(TIMER_TICK_MS, self.update_timer)
        self._add_after_job(self._timer_job_id)

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
            messagebox.showinfo("提示", "已经是最后一题了！", parent=self)

    def exam_prev_question(self) -> None:
        if self.engine is None:
            return
        if self.engine.has_prev():
            self.engine.prev_question()
            self.load_exam_question()
        else:
            messagebox.showinfo("提示", "已经是第一题了！", parent=self)

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
        # P1-6: 标记只改变当前题状态，增量更新当前按钮即可
        self.panel._update_single_nav_button(self.engine.get_current_index())

    # ------------------------------------------------------------------
    # 交卷与报告
    # ------------------------------------------------------------------

    def submit_exam(self, force: bool = False) -> None:
        if not force and not messagebox.askyesno(
            "确认交卷", "确定要交卷吗？\n\n提交后将无法修改答案。", parent=self
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

        # P2-3: 交卷后重置 UI，允许用户在同实例中重新开考
        # （此前 start_btn 永久禁用，用户必须切 tab 才能再考一次）
        self._reset_exam_ui()

    def _reset_exam_ui(self) -> None:
        """交卷后清理考试 UI，恢复初始状态以便重新开考。"""
        if self.panel is not None:
            self.panel.destroy()
            self.panel = None
        self.exam_container.pack_forget()
        self.start_btn.configure(state=tk.NORMAL, bg=theme.BTN_PRIMARY)

    def _save_exam_history(self, report: dict[str, Any]) -> None:
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
        # P2-4: 统一用 save_safe 提示保存失败，避免静默丢数据
        if not self.app_state.save_safe():
            messagebox.showwarning(
                "保存失败",
                "考试历史保存失败，请检查磁盘空间或文件权限。",
                parent=self,
            )
        # P0-6: 保存后刷新历史卡片，让用户立即看到本次成绩
        self._refresh_history_view()

    def show_exam_report(self, report: dict[str, Any]) -> None:
        """显示考试成绩报告对话框。"""
        dialog = ExamReportDialog(self, report, on_add_wrong=self.add_wrong_to_book)
        dialog.show()

    def add_wrong_to_book(self, report: dict[str, Any]) -> int:
        """把报告中的错题加入错题本，返回本次新增数量（供报告对话框防重复点击）。"""
        added = 0
        for q in report["wrong_questions"]:
            q_num = q.number
            if not self.app_state.is_wrong_question(q_num):
                self.app_state.add_wrong_question(q_num)
                added += 1

        # P2-4: 统一用 save_safe 提示保存失败
        if not self.app_state.save_safe():
            messagebox.showwarning(
                "保存失败",
                "错题保存失败，请检查磁盘空间或文件权限。",
                parent=self,
            )
        else:
            messagebox.showinfo("成功", f"已将 {added} 道错题加入错题本！", parent=self)
        return added
