import tkinter as tk
from tkinter import ttk, messagebox

from .theme import (
    BG_PAGE, BG_CARD, BG_INPUT, BG_SELECT,
    BORDER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT, ACCENT_HOVER, ACCENT_LIGHT, ACCENT_BORDER,
    GREEN, GREEN_BG, GREEN_BORDER, GREEN_TEXT,
    RED, RED_BG, RED_BORDER, RED_TEXT,
    YELLOW, YELLOW_BG, YELLOW_BORDER, YELLOW_TEXT,
    PURPLE, PURPLE_BG, PURPLE_BORDER, PURPLE_TEXT,
    BTN_PRIMARY, BTN_PRIMARY_HOVER, BTN_PRIMARY_ACTIVE,
    BTN_NORMAL, BTN_NORMAL_FG, BTN_NORMAL_HOVER, BTN_NORMAL_ACTIVE,
    BTN_DISABLED, BTN_DISABLED_FG,
    SELECTED_BG, SELECTED_TEXT,
    CORRECT_BG, CORRECT_TEXT, CORRECT_HINT_BG, CORRECT_HINT_TEXT,
    WRONG_BG, WRONG_TEXT,
    font_ui, font_ui_semibold,
)
from quiz_engine import QuizEngine
from .base_mode import BaseMode
from .option_row import OptionRow


class ReviewMode(BaseMode):
    def __init__(self, parent, questions, data_manager=None, progress=None):
        super().__init__(parent, questions, data_manager, progress)
        self.showing_answer = False
        self.auto_show_answer = False

        self.engine = QuizEngine(questions)
        self.engine.questions_queue = list(questions)
        self.current_index = 0
        self._setup_mode_ui()
        self.load_question()
        self._bind_keyboard()

    def _setup_mode_ui(self):
        self.configure(style='TFrame')

        toolbar = tk.Frame(self, bg=BG_PAGE)
        toolbar.pack(fill=tk.X, pady=(0, 12))

        toolbar_left = tk.Frame(toolbar, bg=BG_PAGE)
        toolbar_left.pack(side=tk.LEFT)

        self.progress_info = tk.Label(
            toolbar_left, text=f"第 1 题 / 共 {len(self.questions)} 题",
            font=font_ui(11), fg=TEXT_SECONDARY, bg=BG_PAGE)
        self.progress_info.pack(side=tk.LEFT, padx=(0, 16))

        self.type_label = tk.Label(
            toolbar_left, text="单选题",
            font=font_ui_semibold(10), fg=ACCENT, bg=BG_PAGE)
        self.type_label.pack(side=tk.LEFT)

        toolbar_right = tk.Frame(toolbar, bg=BG_PAGE)
        toolbar_right.pack(side=tk.RIGHT)

        self.auto_var = tk.BooleanVar(value=False)
        auto_check = tk.Checkbutton(
            toolbar_right, text="自动显示答案",
            variable=self.auto_var,
            command=self._toggle_auto_show,
            font=font_ui(10), fg=TEXT_SECONDARY, bg=BG_PAGE,
            selectcolor=BG_CARD, activebackground=BG_PAGE,
            activeforeground=ACCENT, cursor='hand2')
        auto_check.pack(side=tk.LEFT, padx=(0, 12))

        jump_label = tk.Label(toolbar_right, text="跳转",
                              font=font_ui(10), fg=TEXT_MUTED, bg=BG_PAGE)
        jump_label.pack(side=tk.LEFT, padx=(0, 4))

        self.jump_var = tk.StringVar()
        jump_entry = tk.Entry(toolbar_right, textvariable=self.jump_var,
                              width=5, font=font_ui(10),
                              bg=BG_CARD, fg=TEXT_PRIMARY,
                              insertbackground=TEXT_PRIMARY,
                              relief=tk.FLAT, bd=2,
                              highlightbackground=BORDER, highlightthickness=1)
        jump_entry.pack(side=tk.LEFT, padx=(0, 4))

        jump_btn = tk.Button(toolbar_right, text="跳转",
                             command=self.jump_to_question,
                             font=font_ui(10), fg=BTN_NORMAL_FG, bg=BTN_NORMAL,
                             activebackground=BTN_NORMAL_HOVER,
                             relief=tk.FLAT, padx=10, pady=3, cursor='hand2')
        jump_btn.pack(side=tk.LEFT, padx=(0, 8))

        prev_btn = tk.Button(toolbar_right, text="上一题 (←)",
                             command=self.prev_question,
                             font=font_ui(10), fg=BTN_NORMAL_FG, bg=BTN_NORMAL,
                             activebackground=BTN_NORMAL_HOVER,
                             relief=tk.FLAT, padx=10, pady=3, cursor='hand2')
        prev_btn.pack(side=tk.LEFT, padx=(0, 4))

        next_btn = tk.Button(toolbar_right, text="下一题 (→)",
                             command=self.next_question,
                             font=font_ui(10), fg=BTN_NORMAL_FG, bg=BTN_NORMAL,
                             activebackground=BTN_NORMAL_HOVER,
                             relief=tk.FLAT, padx=10, pady=3, cursor='hand2')
        next_btn.pack(side=tk.LEFT)

        question_card = tk.Frame(self, bg=BG_CARD, highlightbackground=BORDER,
                                 highlightthickness=1)
        question_card.pack(fill=tk.X, pady=(0, 12))

        q_inner = tk.Frame(question_card, bg=BG_CARD)
        q_inner.pack(fill=tk.BOTH, expand=True, padx=20, pady=16)

        self.review_question_text = tk.Text(
            q_inner, height=4, wrap=tk.WORD,
            font=font_ui(12), bg=BG_CARD, fg=TEXT_PRIMARY,
            relief=tk.FLAT, padx=0, pady=0,
            selectbackground=BG_SELECT, insertbackground=TEXT_PRIMARY)
        self.review_question_text.pack(fill=tk.X)
        self.review_question_text.config(state=tk.DISABLED)

        options_card = tk.Frame(self, bg=BG_CARD, highlightbackground=BORDER,
                                highlightthickness=1)
        options_card.pack(fill=tk.X, pady=(0, 12))

        opt_inner = tk.Frame(options_card, bg=BG_CARD)
        opt_inner.pack(fill=tk.BOTH, expand=True, padx=20, pady=14)

        self.review_option_rows = []
        for letter in ['A', 'B', 'C', 'D', 'E', 'F']:
            row = OptionRow(opt_inner, letter=letter)
            row.pack(fill=tk.X, pady=2)
            self.review_option_rows.append(row)
            if ord(letter) - ord('A') >= 4:
                row.pack_forget()

        answer_card = tk.Frame(self, bg=BG_CARD, highlightbackground=BORDER,
                               highlightthickness=1)
        answer_card.pack(fill=tk.BOTH, expand=True)

        ans_inner = tk.Frame(answer_card, bg=BG_CARD)
        ans_inner.pack(fill=tk.BOTH, expand=True, padx=20, pady=14)

        ans_top = tk.Frame(ans_inner, bg=BG_CARD)
        ans_top.pack(fill=tk.X, pady=(0, 8))

        self.answer_label = tk.Label(ans_top, text="点击下方按钮显示答案",
                                     font=font_ui(11), fg=TEXT_MUTED, bg=BG_CARD)
        self.answer_label.pack(side=tk.LEFT)

        exp_container = tk.Frame(ans_inner, bg=BG_CARD)
        exp_container.pack(fill=tk.BOTH, expand=True)

        exp_scrollbar = tk.Scrollbar(exp_container)
        exp_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.review_explanation_text = tk.Text(
            exp_container, wrap=tk.WORD,
            font=font_ui(11), bg=BG_CARD, fg=TEXT_SECONDARY,
            relief=tk.FLAT, padx=0, pady=0,
            yscrollcommand=exp_scrollbar.set,
            selectbackground=BG_SELECT, insertbackground=TEXT_PRIMARY)
        self.review_explanation_text.pack(fill=tk.BOTH, expand=True)
        exp_scrollbar.config(command=self.review_explanation_text.yview)
        self.review_explanation_text.config(state=tk.DISABLED)

        action_bar = tk.Frame(self, bg=BG_PAGE)
        action_bar.pack(fill=tk.X, pady=(12, 0))

        self.toggle_answer_btn = tk.Button(
            action_bar, text="显示答案 (Space)",
            command=self.toggle_answer,
            font=font_ui_semibold(11), fg='#ffffff', bg=PURPLE,
            activebackground='#7c3aed', activeforeground='#ffffff',
            relief=tk.FLAT, width=16, padx=16, pady=6, cursor='hand2')
        self.toggle_answer_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.favorite_btn = tk.Button(
            action_bar, text="收藏",
            command=self.toggle_favorite,
            font=font_ui(10), fg=BTN_NORMAL_FG, bg=BTN_NORMAL,
            activebackground=BTN_NORMAL_HOVER,
            relief=tk.FLAT, padx=12, pady=5, cursor='hand2')
        self.favorite_btn.pack(side=tk.LEFT)

    def _on_key_press(self, event):
        keysym = event.keysym

        if keysym == 'space':
            self.toggle_answer()
            return 'break'

        # 导航键（Left/Right）交给基类处理（TD-06: 复用 super() 避免重复）
        return super()._on_key_press(event)

    def _toggle_auto_show(self):
        self.auto_show_answer = self.auto_var.get()
        if self.auto_show_answer and not self.showing_answer:
            self.toggle_answer()

    def load_question(self):
        if 0 <= self.current_index < len(self.engine.questions_queue):
            question = self.engine.questions_queue[self.current_index]
        else:
            return

        self.review_question_text.config(state=tk.NORMAL)
        self.review_question_text.delete(1.0, tk.END)
        self.review_question_text.insert(tk.END,
                                         f"{question.get('number')}. {question.get('content')}")
        self.review_question_text.config(state=tk.DISABLED)

        # 显示题目类型
        q_type = question.get('type', 'single')
        if q_type == 'multiple':
            self.type_label.configure(text="多选题", fg=YELLOW)
        else:
            self.type_label.configure(text="单选题", fg=ACCENT)

        options = question.get('options', [])
        for i in range(6):
            if i < len(options):
                self.review_option_rows[i].pack(fill=tk.X, pady=2)
                self.review_option_rows[i].update_text(options[i].get('text', ''))
                self.review_option_rows[i].reset()
            else:
                self.review_option_rows[i].pack_forget()

        self.showing_answer = False
        self.answer_label.configure(text="点击下方按钮显示答案", fg=TEXT_MUTED)
        self.review_explanation_text.config(state=tk.NORMAL)
        self.review_explanation_text.delete(1.0, tk.END)
        self.review_explanation_text.config(state=tk.DISABLED)
        self.toggle_answer_btn.configure(text="显示答案 (Space)")

        self.jump_var.set(str(self.current_index + 1))
        self.progress_info.configure(
            text=f"第 {self.current_index + 1} 题 / 共 {len(self.questions)} 题")

        self._sync_favorite_button()

        if self.auto_show_answer:
            job_id = self.after(100, self.toggle_answer)
            self._add_after_job(job_id)

    def toggle_answer(self):
        question = self.engine.questions_queue[self.current_index]

        if not self.showing_answer:
            self.showing_answer = True
            self.answer_label.configure(
                text=f"正确答案: {question.get('answer', '未知')}", fg=GREEN)
            self.review_explanation_text.config(state=tk.NORMAL)
            self.review_explanation_text.delete(1.0, tk.END)
            explanation = question.get('explanation', '暂无解析')
            self.review_explanation_text.insert(tk.END, explanation)
            self.review_explanation_text.config(state=tk.DISABLED)
            self.toggle_answer_btn.configure(text="隐藏答案 (Space)")

            correct_answer = question.get('answer', '')
            options = question.get('options', [])
            for i, opt in enumerate(options):
                letter = opt.get('letter', chr(ord('A') + i))
                if letter in correct_answer:
                    self.review_option_rows[i].reveal_correct()
                else:
                    self.review_option_rows[i].reset()
        else:
            self.showing_answer = False
            self.answer_label.configure(text="点击下方按钮显示答案", fg=TEXT_MUTED)
            self.review_explanation_text.config(state=tk.NORMAL)
            self.review_explanation_text.delete(1.0, tk.END)
            self.review_explanation_text.config(state=tk.DISABLED)
            self.toggle_answer_btn.configure(text="显示答案 (Space)")

            options = question.get('options', [])
            for i in range(len(options)):
                self.review_option_rows[i].reset()

    def next_question(self):
        if self.current_index < len(self.engine.questions_queue) - 1:
            self.current_index += 1
            self.load_question()

    def prev_question(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.load_question()

    def jump_to_question(self):
        try:
            num = int(self.jump_var.get())
            if 1 <= num <= len(self.questions):
                self.current_index = num - 1
                self.load_question()
            else:
                messagebox.showerror("错误", f"请输入 1-{len(self.questions)} 之间的题号！")
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字！")

    def toggle_favorite(self):
        if not self.data_manager or not self.progress:
            return

        question = self.engine.questions_queue[self.current_index]
        q_num = question.get('number')
        favorites = self.progress.get('favorites', [])

        if q_num in favorites:
            favorites.remove(q_num)
        else:
            favorites.append(q_num)

        self.progress['favorites'] = favorites
        self.data_manager.save_progress(self.progress)
        self._sync_favorite_button()

    def _sync_favorite_button(self):
        """根据当前题是否已收藏，更新按钮文字与配色作为静默反馈。"""
        if not self.engine or not self.progress:
            return
        if self.current_index >= len(self.engine.questions_queue):
            return
        q_num = self.engine.questions_queue[self.current_index].get('number')
        is_fav = q_num in self.progress.get('favorites', [])
        if is_fav:
            self.favorite_btn.configure(text="已收藏 ✓", fg=ACCENT, bg=ACCENT_LIGHT)
        else:
            self.favorite_btn.configure(text="收藏", fg=BTN_NORMAL_FG, bg=BTN_NORMAL)
