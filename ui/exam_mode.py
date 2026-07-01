import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import List, Dict, Any, Set

from .theme import Theme, font_ui, font_ui_semibold, font_mono

from quiz_engine import QuizEngine
from .base_mode import BaseMode
from .option_row import OptionRow

theme = Theme()


class ExamMode(BaseMode):
    def __init__(
        self, parent, questions: List[Dict[str, Any]], data_manager, progress: Any
    ) -> None:
        super().__init__(parent, questions, data_manager, progress)
        self.engine = None
        self.timer_running = False
        self.time_remaining = 0
        self.exam_total_seconds = 0
        self.exam_answers: Dict[int, str] = {}
        self.exam_marked: Set[int] = set()

        self._setup_mode_ui()
        self._bind_keyboard()

    def _setup_mode_ui(self):
        self.configure(style="TFrame")

        settings_card = tk.Frame(
            self, bg=theme.BG_CARD, highlightbackground=theme.BORDER, highlightthickness=1
        )
        settings_card.pack(fill=tk.X, pady=(0, 16))

        s_inner = tk.Frame(settings_card, bg=theme.BG_CARD)
        s_inner.pack(fill=tk.BOTH, expand=True, padx=24, pady=20)

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

        self.start_btn = tk.Button(
            settings_row,
            text="开始考试",
            command=self.start_exam,
            font=font_ui_semibold(11),
            fg="#ffffff",
            bg=theme.BTN_PRIMARY,
            activebackground=theme.BTN_PRIMARY_ACTIVE,
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=24,
            pady=6,
            cursor="hand2",
        )
        self.start_btn.pack(side=tk.RIGHT)

        self.exam_container = tk.Frame(self, bg=theme.BG_PAGE)

        timer_bar = tk.Frame(
            self.exam_container,
            bg=theme.BG_CARD,
            highlightbackground=theme.BORDER,
            highlightthickness=1,
        )
        timer_bar.pack(fill=tk.X, pady=(0, 12))

        timer_inner = tk.Frame(timer_bar, bg=theme.BG_CARD)
        timer_inner.pack(fill=tk.BOTH, expand=True, padx=24, pady=12)

        timer_left = tk.Frame(timer_inner, bg=theme.BG_CARD)
        timer_left.pack(side=tk.LEFT)

        self.timer_label = tk.Label(
            timer_left, text="60:00", font=font_mono(20), fg=theme.RED, bg=theme.BG_CARD
        )
        self.timer_label.pack(side=tk.LEFT, padx=(0, 8))

        timer_hint = tk.Label(
            timer_left, text="剩余时间", font=font_ui(10), fg=theme.TEXT_MUTED, bg=theme.BG_CARD
        )
        timer_hint.pack(side=tk.LEFT)

        self.exam_progress_label = tk.Label(
            timer_inner,
            text="第 0 / 100 题",
            font=font_ui(11),
            fg=theme.TEXT_SECONDARY,
            bg=theme.BG_CARD,
        )
        self.exam_progress_label.pack(side=tk.RIGHT)

        self.exam_type_label = tk.Label(
            timer_inner, text="", font=font_ui_semibold(10), fg=theme.ACCENT, bg=theme.BG_CARD
        )
        self.exam_type_label.pack(side=tk.RIGHT, padx=(0, 16))

        main_paned = tk.PanedWindow(
            self.exam_container,
            orient=tk.HORIZONTAL,
            bg=theme.BG_PAGE,
            sashrelief=tk.FLAT,
            sashwidth=4,
        )
        main_paned.pack(fill=tk.BOTH, expand=True)

        left_panel = tk.Frame(main_paned, bg=theme.BG_PAGE)
        main_paned.add(left_panel, minsize=600)

        question_card = tk.Frame(
            left_panel, bg=theme.BG_CARD, highlightbackground=theme.BORDER, highlightthickness=1
        )
        question_card.pack(fill=tk.X, pady=(0, 12))

        q_inner = tk.Frame(question_card, bg=theme.BG_CARD)
        q_inner.pack(fill=tk.BOTH, expand=True, padx=20, pady=16)

        self.exam_question_text = tk.Text(
            q_inner,
            height=4,
            wrap=tk.WORD,
            font=font_ui(12),
            bg=theme.BG_CARD,
            fg=theme.TEXT_PRIMARY,
            relief=tk.FLAT,
            padx=0,
            pady=0,
            selectbackground=theme.BG_SELECT,
            insertbackground=theme.TEXT_PRIMARY,
        )
        self.exam_question_text.pack(fill=tk.X)
        self.exam_question_text.config(state=tk.DISABLED)

        options_card = tk.Frame(
            left_panel, bg=theme.BG_CARD, highlightbackground=theme.BORDER, highlightthickness=1
        )
        options_card.pack(fill=tk.X, pady=(0, 12))

        opt_inner = tk.Frame(options_card, bg=theme.BG_CARD)
        opt_inner.pack(fill=tk.BOTH, expand=True, padx=20, pady=14)

        self.exam_option_cards = []
        for idx in range(6):
            letter = chr(ord("A") + idx)
            row = OptionRow(
                opt_inner,
                letter=letter,
                on_click=lambda sel: self.exam_select_option_by_letter(sel),
                wraplength=550,
            )
            row.pack(fill=tk.X, pady=3)
            self.exam_option_cards.append(
                {
                    "row": row,
                    "var": tk.IntVar(value=0),
                    "letter": letter,
                }
            )

        action_bar = tk.Frame(left_panel, bg=theme.BG_PAGE)
        action_bar.pack(fill=tk.X, pady=(0, 8))

        btn_left = tk.Frame(action_bar, bg=theme.BG_PAGE)
        btn_left.pack(side=tk.LEFT)

        prev_exam_btn = tk.Button(
            btn_left,
            text="上一题 (←)",
            command=self.exam_prev_question,
            font=font_ui(10),
            fg=theme.BTN_NORMAL_FG,
            bg=theme.BTN_NORMAL,
            activebackground=theme.BTN_NORMAL_HOVER,
            relief=tk.FLAT,
            padx=12,
            pady=5,
            cursor="hand2",
        )
        prev_exam_btn.pack(side=tk.LEFT, padx=(0, 4))

        next_exam_btn = tk.Button(
            btn_left,
            text="下一题 (→)",
            command=self.exam_next_question,
            font=font_ui(10),
            fg=theme.BTN_NORMAL_FG,
            bg=theme.BTN_NORMAL,
            activebackground=theme.BTN_NORMAL_HOVER,
            relief=tk.FLAT,
            padx=12,
            pady=5,
            cursor="hand2",
        )
        next_exam_btn.pack(side=tk.LEFT)

        mark_btn = tk.Button(
            action_bar,
            text="标记 (M)",
            command=self.toggle_mark_current,
            font=font_ui(10),
            fg=theme.YELLOW,
            bg=theme.YELLOW_BG,
            activebackground=theme.YELLOW_BORDER,
            relief=tk.FLAT,
            padx=12,
            pady=5,
            cursor="hand2",
        )
        mark_btn.pack(side=tk.LEFT, padx=(8, 0))

        submit_exam_btn = tk.Button(
            action_bar,
            text="交卷",
            command=self.submit_exam,
            font=font_ui_semibold(11),
            fg="#ffffff",
            bg=theme.RED,
            activebackground="#dc2626",
            relief=tk.FLAT,
            padx=20,
            pady=6,
            cursor="hand2",
        )
        submit_exam_btn.pack(side=tk.RIGHT)

        nav_panel = tk.Frame(
            main_paned, bg=theme.BG_CARD, highlightbackground=theme.BORDER, highlightthickness=1
        )
        main_paned.add(nav_panel, minsize=180)

        nav_inner = tk.Frame(nav_panel, bg=theme.BG_CARD)
        nav_inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        tk.Label(
            nav_inner,
            text="题号导航",
            font=font_ui_semibold(11),
            fg=theme.TEXT_PRIMARY,
            bg=theme.BG_CARD,
        ).pack(anchor=tk.W, pady=(0, 8))

        tk.Label(
            nav_inner,
            text="● 已答  ○ 未答  ★ 标记",
            font=font_ui(9),
            fg=theme.TEXT_MUTED,
            bg=theme.BG_CARD,
        ).pack(anchor=tk.W, pady=(0, 8))

        nav_scroll = tk.Scrollbar(nav_inner)
        nav_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.nav_canvas = tk.Canvas(
            nav_inner, bg=theme.BG_CARD, highlightthickness=0, yscrollcommand=nav_scroll.set
        )
        self.nav_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        nav_scroll.config(command=self.nav_canvas.yview)

        self.nav_frame = tk.Frame(self.nav_canvas, bg=theme.BG_CARD)
        self.nav_canvas.create_window((0, 0), window=self.nav_frame, anchor=tk.NW)

        self.nav_buttons = []

    def _on_key_press(self, event):
        if self.engine is None or not self.engine.get_current_question():
            return

        key = event.char.upper() if event.char else ""
        keysym = event.keysym

        if key and key in "ABCDEF":
            card_idx = ord(key) - ord("A")
            options_count = len(self.engine.get_current_question().get("options", []))
            if card_idx < options_count:
                self.exam_select_option_by_letter(key)
            return "break"

        if key and key in "123456":
            card_idx = int(key) - 1
            options_count = len(self.engine.get_current_question().get("options", []))
            if card_idx < options_count:
                letter = chr(ord("A") + card_idx)
                self.exam_select_option_by_letter(letter)
            return "break"

        if keysym == "Left":
            self.exam_prev_question()
            return "break"

        if keysym == "Right":
            self.exam_next_question()
            return "break"

        if key == "M":
            self.toggle_mark_current()
            return "break"

    def _build_nav_buttons(self, total):
        for btn in self.nav_buttons:
            btn.destroy()
        self.nav_buttons = []

        cols = 5
        for i in range(total):
            row = i // cols
            col = i % cols

            btn = tk.Label(
                self.nav_frame,
                text=str(i + 1),
                font=font_ui(10),
                width=3,
                height=1,
                bg=theme.BG_INPUT,
                fg=theme.TEXT_SECONDARY,
                cursor="hand2",
            )
            btn.grid(row=row, column=col, padx=2, pady=2)
            btn.bind("<Button-1>", lambda e, idx=i: self.jump_to_question(idx))
            self.nav_buttons.append(btn)

        self.nav_frame.update_idletasks()
        self.nav_canvas.config(scrollregion=self.nav_canvas.bbox(tk.ALL))

    def _update_nav_buttons(self):
        if self.engine is None:
            return
        current = self.engine.get_current_index()  # TD-15: 显式接口
        for i, btn in enumerate(self.nav_buttons):
            if i == current:
                bg = theme.ACCENT
                fg = theme.SELECTED_TEXT
            elif i in self.exam_answers:
                bg = theme.GREEN_BG
                fg = theme.GREEN_TEXT
            else:
                bg = theme.BG_INPUT
                fg = theme.TEXT_SECONDARY

            if i in self.exam_marked:
                text = f"★{i + 1}"
            else:
                text = str(i + 1)

            btn.configure(text=text, bg=bg, fg=fg)

    def toggle_mark_current(self) -> None:
        if self.engine is None:
            return
        idx = self.engine.get_current_index()  # TD-15: 显式接口
        if idx in self.exam_marked:
            self.exam_marked.remove(idx)
        else:
            self.exam_marked.add(idx)
        self._update_nav_buttons()

    def jump_to_question(self, idx: int) -> None:
        if self.engine is None:
            return
        if 0 <= idx < self.engine.queue_length():  # TD-15: 显式接口
            self.engine.set_current_index(idx)  # TD-15: 显式接口
            self.load_exam_question()

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
        self.exam_answers = {}
        self.exam_marked = set()

        self.exam_total_seconds = duration * 60
        self.time_remaining = self.exam_total_seconds
        self.timer_running = True

        self.start_btn.configure(state=tk.DISABLED, bg=theme.BTN_DISABLED)
        self.exam_container.pack(fill=tk.BOTH, expand=True, padx=0, pady=5)

        self._build_nav_buttons(self.engine.queue_length())  # TD-15: 显式接口
        self.load_exam_question()
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

        minutes = self.time_remaining // 60
        seconds = self.time_remaining % 60
        time_str = f"{minutes:02d}:{seconds:02d}"
        self.timer_label.configure(text=time_str)

        if self.time_remaining <= 300:
            color = theme.RED if self.time_remaining % 2 == 0 else "#b91c1c"
            self.timer_label.configure(fg=color)

        job_id = self.after(1000, self.update_timer)
        self._add_after_job(job_id)

    def load_exam_question(self) -> None:
        if self.engine is None:
            return
        question = self.engine.get_current_question()
        if not question:
            return

        self.exam_question_text.config(state=tk.NORMAL)
        self.exam_question_text.delete(1.0, tk.END)
        self.exam_question_text.insert(
            tk.END, f"{self.engine.get_current_index() + 1}. {question.get('content')}"
        )  # TD-15: 显式接口
        self.exam_question_text.config(state=tk.DISABLED)

        # 显示题目类型
        q_type = question.get("type", "single")
        if q_type == "multiple":
            self.exam_type_label.configure(text="多选题", fg=theme.YELLOW)
        else:
            self.exam_type_label.configure(text="单选题", fg=theme.ACCENT)

        options_count = len(question.get("options", []))
        for i, item in enumerate(self.exam_option_cards):
            if i < options_count:
                item["row"].pack(fill=tk.X, pady=3)
                opt = question["options"][i]
                item["row"].update_text(opt.get("text", ""))
                item["var"].set(0)
                item["row"].reset()
            else:
                item["row"].pack_forget()

        current_idx = self.engine.get_current_index()  # TD-15: 显式接口
        if current_idx in self.exam_answers:
            answered_letters = self.exam_answers[current_idx]
            for i, item in enumerate(self.exam_option_cards):
                letter = chr(ord("A") + i)
                if letter in answered_letters:
                    item["var"].set(1)
                    item["row"].set_selected(True)

        progress = self.engine.get_progress()
        self.exam_progress_label.configure(
            text=f"第 {progress['current']} / {progress['total']} 题"
        )

        self._update_nav_buttons()

    def exam_select_option_by_letter(self, letter: str) -> None:
        """点击或键盘触发选项选择。"""
        if self.engine is None:
            return
        idx = ord(letter) - ord("A")
        if not (0 <= idx < len(self.exam_option_cards)):
            return

        item = self.exam_option_cards[idx]
        var = item["var"]
        row = item["row"]

        current_idx = self.engine.get_current_index()  # TD-15: 显式接口
        question = self.engine.get_current_question()
        if question is None:
            return
        is_multiple = question.get("type") == "multiple"
        options_count = len(question.get("options", []))

        if is_multiple:
            # 多选题：切换当前选项，不影响其他选项
            if var.get() == 1:
                var.set(0)
                row.set_selected(False)
            else:
                var.set(1)
                row.set_selected(True)

            # 收集所有已选选项
            selected = []
            for i, it in enumerate(self.exam_option_cards):
                if i < options_count and it["var"].get():
                    selected.append(chr(ord("A") + i))
            selected.sort()
            if selected:
                self.exam_answers[current_idx] = "".join(selected)
            elif current_idx in self.exam_answers:
                del self.exam_answers[current_idx]
        else:
            # 单选题：点击一个取消其他
            if var.get() == 1:
                var.set(0)
                row.set_selected(False)
                if current_idx in self.exam_answers:
                    del self.exam_answers[current_idx]
            else:
                for i, it in enumerate(self.exam_option_cards):
                    if i < options_count and it["var"].get():
                        it["var"].set(0)
                        it["row"].set_selected(False)
                var.set(1)
                row.set_selected(True)
                self.exam_answers[current_idx] = letter

        self._update_nav_buttons()

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

    def submit_exam(self, force: bool = False) -> None:
        if not force and not messagebox.askyesno(
            "确认交卷", "确定要交卷吗？\n\n提交后将无法修改答案。"
        ):
            return

        self._cancel_all_after_jobs()
        self.timer_running = False

        if self.engine is None:
            return

        for idx, letter in self.exam_answers.items():
            self.engine.record_exam_answer(idx, letter)

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
        report_window = tk.Toplevel(self)
        report_window.title("考试成绩报告")
        report_window.geometry("600x550")
        report_window.configure(bg=theme.BG_PAGE)
        report_window.transient(self.winfo_toplevel())
        report_window.grab_set()

        report_window.update_idletasks()
        width = report_window.winfo_width()
        height = report_window.winfo_height()
        x = (report_window.winfo_screenwidth() // 2) - (width // 2)
        y = (report_window.winfo_screenheight() // 2) - (height // 2)
        report_window.geometry(f"{width}x{height}+{x}+{y}")

        header = tk.Frame(
            report_window, bg=theme.BG_CARD, highlightbackground=theme.BORDER, highlightthickness=1
        )
        header.pack(fill=tk.X, padx=20, pady=(20, 0))

        h_inner = tk.Frame(header, bg=theme.BG_CARD)
        h_inner.pack(fill=tk.BOTH, expand=True, padx=24, pady=20)

        tk.Label(
            h_inner,
            text="考试成绩报告",
            font=font_ui_semibold(18),
            fg=theme.TEXT_PRIMARY,
            bg=theme.BG_CARD,
        ).pack(anchor=tk.W)

        tk.Label(
            h_inner,
            text=f"完成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            font=font_ui(10),
            fg=theme.TEXT_MUTED,
            bg=theme.BG_CARD,
        ).pack(anchor=tk.W, pady=(4, 0))

        accuracy = report["accuracy"]
        acc_color = (
            theme.GREEN if accuracy >= 80 else (theme.YELLOW if accuracy >= 60 else theme.RED)
        )

        score_card = tk.Frame(
            report_window, bg=theme.BG_CARD, highlightbackground=theme.BORDER, highlightthickness=1
        )
        score_card.pack(fill=tk.X, padx=20, pady=16)

        score_inner = tk.Frame(score_card, bg=theme.BG_CARD)
        score_inner.pack(fill=tk.BOTH, expand=True, padx=24, pady=20)

        acc_frame = tk.Frame(score_inner, bg=theme.BG_CARD)
        acc_frame.pack(fill=tk.X, pady=(0, 16))

        tk.Label(
            acc_frame, text=f"{accuracy:.1f}%", font=font_mono(32), fg=acc_color, bg=theme.BG_CARD
        ).pack(side=tk.LEFT, padx=(0, 12))

        tk.Label(
            acc_frame, text="正确率", font=font_ui(12), fg=theme.TEXT_MUTED, bg=theme.BG_CARD
        ).pack(side=tk.LEFT)

        stats_grid = tk.Frame(score_inner, bg=theme.BG_CARD)
        stats_grid.pack(fill=tk.X)

        stats_data = [
            ("总题数", f"{report['total_questions']}", theme.TEXT_SECONDARY),
            ("正确", f"{report['correct']}", theme.GREEN),
            ("错误", f"{report['wrong']}", theme.RED),
            ("用时", report["time_used"], theme.ACCENT),
        ]

        for i, (label, value, color) in enumerate(stats_data):
            stat_item = tk.Frame(stats_grid, bg=theme.BG_INPUT, padx=16, pady=10)
            stat_item.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0 if i == 0 else 4, 4))

            tk.Label(
                stat_item, text=value, font=font_ui_semibold(14), fg=color, bg=theme.BG_INPUT
            ).pack()

            tk.Label(
                stat_item, text=label, font=font_ui(9), fg=theme.TEXT_MUTED, bg=theme.BG_INPUT
            ).pack(pady=(2, 0))

        if report["wrong_questions"]:
            wrong_card = tk.Frame(
                report_window,
                bg=theme.BG_CARD,
                highlightbackground=theme.BORDER,
                highlightthickness=1,
            )
            wrong_card.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 16))

            w_inner = tk.Frame(wrong_card, bg=theme.BG_CARD)
            w_inner.pack(fill=tk.BOTH, expand=True, padx=24, pady=16)

            tk.Label(
                w_inner,
                text=f"错题 ({len(report['wrong_questions'])} 题)",
                font=font_ui_semibold(12),
                fg=theme.RED,
                bg=theme.BG_CARD,
            ).pack(anchor=tk.W, pady=(0, 8))

            wrong_list_frame = tk.Frame(w_inner, bg=theme.BG_CARD)
            wrong_list_frame.pack(fill=tk.BOTH, expand=True)

            scrollbar = tk.Scrollbar(wrong_list_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            wrong_text = tk.Text(
                wrong_list_frame,
                height=5,
                wrap=tk.WORD,
                font=font_ui(10),
                bg=theme.BG_INPUT,
                fg=theme.TEXT_SECONDARY,
                relief=tk.FLAT,
                padx=12,
                pady=8,
                yscrollcommand=scrollbar.set,
                selectbackground=theme.BG_SELECT,
                insertbackground=theme.TEXT_PRIMARY,
            )
            wrong_text.pack(fill=tk.BOTH, expand=True)
            scrollbar.config(command=wrong_text.yview)

            for q in report["wrong_questions"][:10]:
                content_preview = q.get("content", "")[:50]
                wrong_text.insert(tk.END, f"第 {q.get('number')} 题: {content_preview}...\n\n")

            wrong_text.config(state=tk.DISABLED)

            add_wrong_btn = tk.Button(
                w_inner,
                text="加入错题本",
                command=lambda: self.add_wrong_to_book(report),
                font=font_ui(10),
                fg="#ffffff",
                bg=theme.RED,
                activebackground="#dc2626",
                relief=tk.FLAT,
                padx=16,
                pady=5,
                cursor="hand2",
            )
            add_wrong_btn.pack(pady=(10, 0))

        close_btn = tk.Button(
            report_window,
            text="关闭",
            command=report_window.destroy,
            font=font_ui_semibold(11),
            fg=theme.BTN_NORMAL_FG,
            bg=theme.BTN_NORMAL,
            activebackground=theme.BTN_NORMAL_ACTIVE,
            relief=tk.FLAT,
            width=12,
            padx=16,
            pady=6,
            cursor="hand2",
        )
        close_btn.pack(pady=(0, 20))

    def add_wrong_to_book(self, report: Dict[str, Any]) -> None:
        added = 0
        for q in report["wrong_questions"]:
            q_num = q.get("number")
            if q_num is not None and not self.app_state.is_wrong_question(q_num):
                self.app_state.add_wrong_question(q_num)
                added += 1

        self.app_state.save()
        messagebox.showinfo("成功", f"已将 {added} 道错题加入错题本！")
