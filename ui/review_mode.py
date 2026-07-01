import tkinter as tk
from tkinter import messagebox
from typing import List, Dict, Any

from .theme import Theme, font_ui, font_ui_semibold

from quiz_engine import QuizEngine
from .base_mode import BaseMode
from .option_row import OptionRow

theme = Theme()


class ReviewMode(BaseMode):
    def __init__(
        self, parent, questions: List[Dict[str, Any]], data_manager=None, progress: Any = None
    ) -> None:
        super().__init__(parent, questions, data_manager, progress)
        self.showing_answer = False
        self.auto_show_answer = False

        self.engine: QuizEngine = QuizEngine(questions)
        self.engine.set_questions_queue(questions)  # TD-15: 显式接口
        self.current_index = 0
        self._setup_mode_ui()
        self.load_question()
        self._bind_keyboard()

    def _setup_mode_ui(self):
        self.configure(style="TFrame")

        toolbar = tk.Frame(self, bg=theme.BG_PAGE)
        toolbar.pack(fill=tk.X, pady=(0, 12))

        toolbar_left = tk.Frame(toolbar, bg=theme.BG_PAGE)
        toolbar_left.pack(side=tk.LEFT)

        self.progress_info = tk.Label(
            toolbar_left,
            text=f"第 1 题 / 共 {len(self.questions)} 题",
            font=font_ui(11),
            fg=theme.TEXT_SECONDARY,
            bg=theme.BG_PAGE,
        )
        self.progress_info.pack(side=tk.LEFT, padx=(0, 16))

        self.type_label = tk.Label(
            toolbar_left,
            text="单选题",
            font=font_ui_semibold(10),
            fg=theme.ACCENT,
            bg=theme.BG_PAGE,
        )
        self.type_label.pack(side=tk.LEFT)

        toolbar_right = tk.Frame(toolbar, bg=theme.BG_PAGE)
        toolbar_right.pack(side=tk.RIGHT)

        self.auto_var = tk.BooleanVar(value=False)
        auto_check = tk.Checkbutton(
            toolbar_right,
            text="自动显示答案",
            variable=self.auto_var,
            command=self._toggle_auto_show,
            font=font_ui(10),
            fg=theme.TEXT_SECONDARY,
            bg=theme.BG_PAGE,
            selectcolor=theme.BG_CARD,
            activebackground=theme.BG_PAGE,
            activeforeground=theme.ACCENT,
            cursor="hand2",
        )
        auto_check.pack(side=tk.LEFT, padx=(0, 12))

        jump_label = tk.Label(
            toolbar_right, text="跳转", font=font_ui(10), fg=theme.TEXT_MUTED, bg=theme.BG_PAGE
        )
        jump_label.pack(side=tk.LEFT, padx=(0, 4))

        self.jump_var = tk.StringVar()
        jump_entry = tk.Entry(
            toolbar_right,
            textvariable=self.jump_var,
            width=5,
            font=font_ui(10),
            bg=theme.BG_CARD,
            fg=theme.TEXT_PRIMARY,
            insertbackground=theme.TEXT_PRIMARY,
            relief=tk.FLAT,
            bd=2,
            highlightbackground=theme.BORDER,
            highlightthickness=1,
        )
        jump_entry.pack(side=tk.LEFT, padx=(0, 4))

        jump_btn = tk.Button(
            toolbar_right,
            text="跳转",
            command=self.jump_to_question,
            font=font_ui(10),
            fg=theme.BTN_NORMAL_FG,
            bg=theme.BTN_NORMAL,
            activebackground=theme.BTN_NORMAL_HOVER,
            relief=tk.FLAT,
            padx=10,
            pady=3,
            cursor="hand2",
        )
        jump_btn.pack(side=tk.LEFT, padx=(0, 8))

        prev_btn = tk.Button(
            toolbar_right,
            text="上一题 (←)",
            command=self.prev_question,
            font=font_ui(10),
            fg=theme.BTN_NORMAL_FG,
            bg=theme.BTN_NORMAL,
            activebackground=theme.BTN_NORMAL_HOVER,
            relief=tk.FLAT,
            padx=10,
            pady=3,
            cursor="hand2",
        )
        prev_btn.pack(side=tk.LEFT, padx=(0, 4))

        next_btn = tk.Button(
            toolbar_right,
            text="下一题 (→)",
            command=self.next_question,
            font=font_ui(10),
            fg=theme.BTN_NORMAL_FG,
            bg=theme.BTN_NORMAL,
            activebackground=theme.BTN_NORMAL_HOVER,
            relief=tk.FLAT,
            padx=10,
            pady=3,
            cursor="hand2",
        )
        next_btn.pack(side=tk.LEFT)

        question_card = tk.Frame(
            self, bg=theme.BG_CARD, highlightbackground=theme.BORDER, highlightthickness=1
        )
        question_card.pack(fill=tk.X, pady=(0, 12))

        q_inner = tk.Frame(question_card, bg=theme.BG_CARD)
        q_inner.pack(fill=tk.BOTH, expand=True, padx=20, pady=16)

        self.review_question_text = tk.Text(
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
        self.review_question_text.pack(fill=tk.X)
        self.review_question_text.config(state=tk.DISABLED)

        options_card = tk.Frame(
            self, bg=theme.BG_CARD, highlightbackground=theme.BORDER, highlightthickness=1
        )
        options_card.pack(fill=tk.X, pady=(0, 12))

        opt_inner = tk.Frame(options_card, bg=theme.BG_CARD)
        opt_inner.pack(fill=tk.BOTH, expand=True, padx=20, pady=14)

        self.review_option_rows = []
        for letter in ["A", "B", "C", "D", "E", "F"]:
            row = OptionRow(opt_inner, letter=letter)
            row.pack(fill=tk.X, pady=2)
            self.review_option_rows.append(row)
            if ord(letter) - ord("A") >= 4:
                row.pack_forget()

        answer_card = tk.Frame(
            self, bg=theme.BG_CARD, highlightbackground=theme.BORDER, highlightthickness=1
        )
        answer_card.pack(fill=tk.BOTH, expand=True)

        ans_inner = tk.Frame(answer_card, bg=theme.BG_CARD)
        ans_inner.pack(fill=tk.BOTH, expand=True, padx=20, pady=14)

        ans_top = tk.Frame(ans_inner, bg=theme.BG_CARD)
        ans_top.pack(fill=tk.X, pady=(0, 8))

        self.answer_label = tk.Label(
            ans_top,
            text="点击下方按钮显示答案",
            font=font_ui(11),
            fg=theme.TEXT_MUTED,
            bg=theme.BG_CARD,
        )
        self.answer_label.pack(side=tk.LEFT)

        exp_container = tk.Frame(ans_inner, bg=theme.BG_CARD)
        exp_container.pack(fill=tk.BOTH, expand=True)

        exp_scrollbar = tk.Scrollbar(exp_container)
        exp_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.review_explanation_text = tk.Text(
            exp_container,
            wrap=tk.WORD,
            font=font_ui(11),
            bg=theme.BG_CARD,
            fg=theme.TEXT_SECONDARY,
            relief=tk.FLAT,
            padx=0,
            pady=0,
            yscrollcommand=exp_scrollbar.set,
            selectbackground=theme.BG_SELECT,
            insertbackground=theme.TEXT_PRIMARY,
        )
        self.review_explanation_text.pack(fill=tk.BOTH, expand=True)
        exp_scrollbar.config(command=self.review_explanation_text.yview)
        self.review_explanation_text.config(state=tk.DISABLED)

        action_bar = tk.Frame(self, bg=theme.BG_PAGE)
        action_bar.pack(fill=tk.X, pady=(12, 0))

        self.toggle_answer_btn = tk.Button(
            action_bar,
            text="显示答案 (Space)",
            command=self.toggle_answer,
            font=font_ui_semibold(11),
            fg="#ffffff",
            bg=theme.PURPLE,
            activebackground="#7c3aed",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            width=16,
            padx=16,
            pady=6,
            cursor="hand2",
        )
        self.toggle_answer_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.favorite_btn = tk.Button(
            action_bar,
            text="收藏",
            command=self.toggle_favorite,
            font=font_ui(10),
            fg=theme.BTN_NORMAL_FG,
            bg=theme.BTN_NORMAL,
            activebackground=theme.BTN_NORMAL_HOVER,
            relief=tk.FLAT,
            padx=12,
            pady=5,
            cursor="hand2",
        )
        self.favorite_btn.pack(side=tk.LEFT)

    def _on_key_press(self, event):
        keysym = event.keysym

        if keysym == "space":
            self.toggle_answer()
            return "break"

        # 导航键（Left/Right）交给基类处理（TD-06: 复用 super() 避免重复）
        return super()._on_key_press(event)

    def _toggle_auto_show(self):
        self.auto_show_answer = self.auto_var.get()
        if self.auto_show_answer and not self.showing_answer:
            self.toggle_answer()

    def load_question(self) -> None:
        if 0 <= self.current_index < self.engine.queue_length():
            question = self.engine.get_question_at(self.current_index)
        else:
            return

        if question is None:
            return

        self.review_question_text.config(state=tk.NORMAL)
        self.review_question_text.delete(1.0, tk.END)
        self.review_question_text.insert(
            tk.END, f"{question.get('number')}. {question.get('content')}"
        )
        self.review_question_text.config(state=tk.DISABLED)

        # 显示题目类型
        q_type = question.get("type", "single")
        if q_type == "multiple":
            self.type_label.configure(text="多选题", fg=theme.YELLOW)
        else:
            self.type_label.configure(text="单选题", fg=theme.ACCENT)

        options = question.get("options", [])
        for i in range(6):
            if i < len(options):
                self.review_option_rows[i].pack(fill=tk.X, pady=2)
                self.review_option_rows[i].update_text(options[i].get("text", ""))
                self.review_option_rows[i].reset()
            else:
                self.review_option_rows[i].pack_forget()

        self.showing_answer = False
        self.answer_label.configure(text="点击下方按钮显示答案", fg=theme.TEXT_MUTED)
        self.review_explanation_text.config(state=tk.NORMAL)
        self.review_explanation_text.delete(1.0, tk.END)
        self.review_explanation_text.config(state=tk.DISABLED)
        self.toggle_answer_btn.configure(text="显示答案 (Space)")

        self.jump_var.set(str(self.current_index + 1))
        self.progress_info.configure(
            text=f"第 {self.current_index + 1} 题 / 共 {len(self.questions)} 题"
        )

        self._sync_favorite_button()

        if self.auto_show_answer:
            job_id = self.after(100, self.toggle_answer)
            self._add_after_job(job_id)

    def toggle_answer(self) -> None:
        question = self.engine.get_question_at(self.current_index)
        if question is None:
            return

        if not self.showing_answer:
            self.showing_answer = True
            self.answer_label.configure(
                text=f"正确答案: {question.get('answer', '未知')}", fg=theme.GREEN
            )
            self.review_explanation_text.config(state=tk.NORMAL)
            self.review_explanation_text.delete(1.0, tk.END)
            explanation = question.get("explanation", "暂无解析")
            self.review_explanation_text.insert(tk.END, explanation)
            self.review_explanation_text.config(state=tk.DISABLED)
            self.toggle_answer_btn.configure(text="隐藏答案 (Space)")

            correct_answer = question.get("answer", "")
            options = question.get("options", [])
            for i, opt in enumerate(options):
                letter = opt.get("letter", chr(ord("A") + i))
                if letter in correct_answer:
                    self.review_option_rows[i].reveal_correct()
                else:
                    self.review_option_rows[i].reset()
        else:
            self.showing_answer = False
            self.answer_label.configure(text="点击下方按钮显示答案", fg=theme.TEXT_MUTED)
            self.review_explanation_text.config(state=tk.NORMAL)
            self.review_explanation_text.delete(1.0, tk.END)
            self.review_explanation_text.config(state=tk.DISABLED)
            self.toggle_answer_btn.configure(text="显示答案 (Space)")

            options = question.get("options", [])
            for i in range(len(options)):
                self.review_option_rows[i].reset()

    def next_question(self) -> None:
        if self.current_index < self.engine.queue_length() - 1:
            self.current_index += 1
            self.load_question()

    def prev_question(self) -> None:
        if self.current_index > 0:
            self.current_index -= 1
            self.load_question()

    def jump_to_question(self) -> None:
        try:
            num = int(self.jump_var.get())
            if 1 <= num <= len(self.questions):
                self.current_index = num - 1
                self.load_question()
            else:
                messagebox.showerror("错误", f"请输入 1-{len(self.questions)} 之间的题号！")
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字！")

    def toggle_favorite(self) -> None:
        if not self.data_manager or not self.progress:
            return

        question = self.engine.get_question_at(self.current_index)
        if question is None:
            return
        q_num = question.get("number")
        if q_num is None:
            return
        self.app_state.toggle_favorite(q_num)
        self.app_state.save()
        self._sync_favorite_button()

    def _sync_favorite_button(self):
        """根据当前题是否已收藏，更新按钮文字与配色作为静默反馈。"""
        if not self.engine or not self.progress:
            return
        if self.current_index >= self.engine.queue_length():
            return
        q_num = self.engine.get_question_at(self.current_index).get("number")
        is_fav = self.app_state.is_favorite(q_num)
        if is_fav:
            self.favorite_btn.configure(text="已收藏 ✓", fg=theme.ACCENT, bg=theme.ACCENT_LIGHT)
        else:
            self.favorite_btn.configure(text="收藏", fg=theme.BTN_NORMAL_FG, bg=theme.BTN_NORMAL)
