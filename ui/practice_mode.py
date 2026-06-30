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


class PracticeMode(BaseMode):
    def __init__(self, parent, questions, data_manager, progress):
        super().__init__(parent, questions, data_manager, progress)
        self.engine = QuizEngine(questions)
        self.selected_answers = []
        self.current_question_type = 'single'
        self.is_answered = False

        self._setup_mode_ui()
        self.start_new_session()
        self._bind_keyboard()

    def _setup_mode_ui(self):
        """构建练习模式 UI（TD-11: 拆分为子方法以提高可读性）。"""
        self.configure(style='TFrame')

        toolbar, self.progress_label, self.type_label = self._create_toolbar(self)
        self._create_toolbar_right(toolbar)
        self._create_progress_bar()
        self._create_question_card()

        content_frame = tk.Frame(self, bg=BG_PAGE)
        content_frame.pack(fill=tk.BOTH, expand=True)
        self._create_options_card(content_frame)
        self._create_action_bar(content_frame)
        self._create_result_card(content_frame)

    def _create_toolbar_right(self, toolbar):
        """工具栏右侧：随机出题复选框 + 重新开始按钮。"""
        toolbar_right = tk.Frame(toolbar, bg=BG_PAGE)
        toolbar_right.pack(side=tk.RIGHT)

        self.shuffle_var = tk.BooleanVar(value=False)
        shuffle_check = tk.Checkbutton(
            toolbar_right, text="随机出题",
            variable=self.shuffle_var, command=self.restart_session,
            font=font_ui(10), fg=TEXT_SECONDARY, bg=BG_PAGE,
            selectcolor=BG_CARD, activebackground=BG_PAGE,
            activeforeground=ACCENT, cursor='hand2')
        shuffle_check.pack(side=tk.LEFT, padx=(0, 8))

        restart_btn = tk.Button(
            toolbar_right, text="重新开始",
            command=self.restart_session,
            font=font_ui(10), fg=BTN_NORMAL_FG, bg=BTN_NORMAL,
            activebackground=BTN_NORMAL_HOVER, activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT, padx=12, pady=4, cursor='hand2')
        restart_btn.pack(side=tk.LEFT)

    def _create_progress_bar(self):
        """顶部进度条。"""
        progress_bg = tk.Frame(self, bg=BORDER, height=3)
        progress_bg.pack(fill=tk.X, pady=(0, 16))
        progress_bg.pack_propagate(False)

        self.progress_bar_fill = tk.Frame(progress_bg, bg=ACCENT, width=0, height=3)
        self.progress_bar_fill.place(x=0, y=0, relheight=1.0)

        self.progress_value = tk.DoubleVar(value=0)

    def _create_question_card(self):
        """题干卡片。"""
        question_card = tk.Frame(self, bg=BG_CARD, highlightbackground=BORDER,
                                 highlightthickness=1)
        question_card.pack(fill=tk.X, pady=(0, 12))

        q_inner = tk.Frame(question_card, bg=BG_CARD)
        q_inner.pack(fill=tk.BOTH, expand=True, padx=20, pady=16)

        self.question_label = tk.Label(
            q_inner, text="",
            font=font_ui(12), fg=TEXT_PRIMARY, bg=BG_CARD,
            wraplength=800, justify=tk.LEFT, anchor=tk.NW)
        self.question_label.pack(fill=tk.BOTH, expand=True)
        self.question_label.bind('<Configure>', self._on_question_resize)

    def _create_options_card(self, content_frame):
        """选项卡片（6 个 OptionRow）。"""
        options_card = tk.Frame(content_frame, bg=BG_CARD, highlightbackground=BORDER,
                                highlightthickness=1)
        options_card.pack(fill=tk.X, pady=(0, 12))

        opt_inner = tk.Frame(options_card, bg=BG_CARD)
        opt_inner.pack(fill=tk.BOTH, expand=True, padx=20, pady=14)

        self.option_cards = []
        for idx in range(6):
            letter = chr(ord('A') + idx)
            card = OptionRow(opt_inner, letter=letter, on_click=self.handle_option_click)
            card.pack(fill=tk.X, pady=4)
            self.option_cards.append(card)

    def _create_action_bar(self, content_frame):
        """操作栏：提交/上一题/下一题 + 统计标签。"""
        action_bar = tk.Frame(content_frame, bg=BG_PAGE)
        action_bar.pack(fill=tk.X, pady=(0, 12))

        btn_left = tk.Frame(action_bar, bg=BG_PAGE)
        btn_left.pack(side=tk.LEFT)

        self.submit_btn = tk.Button(
            btn_left, text="提交答案 (Enter)",
            command=self.submit_answer,
            font=font_ui_semibold(11), fg='#ffffff', bg=BTN_PRIMARY,
            activebackground=BTN_PRIMARY_ACTIVE, activeforeground='#ffffff',
            relief=tk.FLAT, width=14, padx=16, pady=6, cursor='hand2')
        self.submit_btn.pack(side=tk.LEFT, padx=(0, 8))

        prev_btn = tk.Button(
            btn_left, text="上一题 (←)",
            command=self.prev_question,
            font=font_ui(10), fg=BTN_NORMAL_FG, bg=BTN_NORMAL,
            activebackground=BTN_NORMAL_HOVER, activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT, padx=12, pady=5, cursor='hand2')
        prev_btn.pack(side=tk.LEFT, padx=(0, 4))

        next_btn = tk.Button(
            btn_left, text="下一题 (→)",
            command=self.next_question,
            font=font_ui(10), fg=BTN_NORMAL_FG, bg=BTN_NORMAL,
            activebackground=BTN_NORMAL_HOVER, activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT, padx=12, pady=5, cursor='hand2')
        next_btn.pack(side=tk.LEFT)

        stats_right = tk.Frame(action_bar, bg=BG_PAGE)
        stats_right.pack(side=tk.RIGHT)

        self.stats_label = tk.Label(
            stats_right, text="正确 0  |  错误 0  |  正确率 0%",
            font=font_ui_semibold(11), fg=ACCENT, bg=BG_PAGE)
        self.stats_label.pack()

    def _create_result_card(self, content_frame):
        """解析卡片：结果标签 + 带滚动条的解析文本。"""
        result_card = tk.Frame(content_frame, bg=BG_CARD, highlightbackground=BORDER,
                               highlightthickness=1)
        result_card.pack(fill=tk.BOTH, expand=True)

        res_inner = tk.Frame(result_card, bg=BG_CARD)
        res_inner.pack(fill=tk.BOTH, expand=True, padx=20, pady=14)

        res_top = tk.Frame(res_inner, bg=BG_CARD)
        res_top.pack(fill=tk.X, pady=(0, 8))

        self.result_label = tk.Label(
            res_top, text="提交答案后查看解析",
            font=font_ui(11), fg=TEXT_MUTED, bg=BG_CARD)
        self.result_label.pack(side=tk.LEFT)

        exp_container = tk.Frame(res_inner, bg=BG_CARD)
        exp_container.pack(fill=tk.BOTH, expand=True)

        exp_scrollbar = tk.Scrollbar(exp_container)
        exp_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.explanation_text = tk.Text(
            exp_container, wrap=tk.WORD,
            font=font_ui(11), bg=BG_CARD, fg=TEXT_SECONDARY,
            relief=tk.FLAT, padx=0, pady=0,
            yscrollcommand=exp_scrollbar.set,
            selectbackground=BG_SELECT, insertbackground=TEXT_PRIMARY)
        self.explanation_text.pack(fill=tk.BOTH, expand=True)
        exp_scrollbar.config(command=self.explanation_text.yview)
        self.explanation_text.config(state=tk.DISABLED)

    def _bind_keyboard(self):
        self.focus_set()
        self.bind('<Key>', self._on_key_press)
        self.bind_all('<Button-1>', self._on_global_click)

    def _on_global_click(self, event):
        try:
            self.focus_set()
        except tk.TclError:
            pass

    def _on_key_press(self, event):
        if not self.engine.get_current_question():
            return

        key = event.char.upper() if event.char else ''
        keysym = event.keysym

        if key and key in 'ABCDEF' and not self.is_answered:
            card_idx = ord(key) - ord('A')
            options_count = len(self.engine.get_current_question().get('options', []))
            if card_idx < options_count:
                self.handle_option_click(key)
            return 'break'

        if key and key in '123456' and not self.is_answered:
            card_idx = int(key) - 1
            options_count = len(self.engine.get_current_question().get('options', []))
            if card_idx < options_count:
                letter = chr(ord('A') + card_idx)
                self.handle_option_click(letter)
            return 'break'

        if keysym == 'Return' and not self.is_answered:
            self.submit_answer()
            return 'break'

        if keysym == 'Left':
            self.prev_question()
            return 'break'

        if keysym == 'Right':
            self.next_question()
            return 'break'

    def handle_option_click(self, letter):
        if self.is_answered:
            return

        card_idx = ord(letter) - ord('A')

        if self.current_question_type == 'single':
            for i, card in enumerate(self.option_cards):
                if i < len(self.engine.get_current_question().get('options', [])):
                    card.set_selected(i == card_idx)
            self.selected_answers = [letter]
        else:
            if letter in self.selected_answers:
                self.selected_answers.remove(letter)
                self.option_cards[card_idx].set_selected(False)
            else:
                self.selected_answers.append(letter)
                self.selected_answers.sort()
                self.option_cards[card_idx].set_selected(True)

    def start_new_session(self):
        shuffle = self.shuffle_var.get()
        self.engine.start_practice_mode(shuffle=shuffle)
        self.selected_answers = []
        self.is_answered = False
        self.load_current_question()

    def restart_session(self):
        self.start_new_session()

    def load_current_question(self):
        question = self.engine.get_current_question()
        if not question:
            messagebox.showinfo("提示", "已完成所有题目！")
            return

        self.question_label.configure(
            text=f"{question.get('number')}. {question.get('content', '')}")

        self.current_question_type = question.get('type', 'single')
        if self.current_question_type == 'single':
            self.type_label.configure(text="单选题", fg=ACCENT)
        else:
            self.type_label.configure(text="多选题", fg=YELLOW)

        options_count = len(question.get('options', []))
        for i, card in enumerate(self.option_cards):
            if i < options_count:
                card.pack(fill=tk.X, pady=3)
                opt = question['options'][i]
                card.update_text(opt.get('text', ''))
                card.reset()
            else:
                card.pack_forget()

        self.result_label.configure(text="提交答案后查看解析", fg=TEXT_MUTED)
        self.explanation_text.config(state=tk.NORMAL)
        self.explanation_text.delete(1.0, tk.END)
        self.explanation_text.config(state=tk.DISABLED)

        self.selected_answers = []
        self.is_answered = False
        self.submit_btn.configure(state=tk.NORMAL, bg=BTN_PRIMARY, text="提交答案 (Enter)")

        progress = self.engine.get_progress()
        self.progress_value.set(progress['percentage'])
        self._update_progress_bar_width()
        self.progress_label.configure(
            text=f"第 {progress['current']} 题 / 共 {progress['total']} 题")

        stats = progress['stats']
        accuracy = (stats['correct'] / stats['total'] * 100) if stats['total'] > 0 else 0
        self.stats_label.configure(
            text=f"正确 {stats['correct']}  |  错误 {stats['wrong']}  |  正确率 {accuracy:.0f}%")

    def _update_progress_bar_width(self):
        self.update_idletasks()
        progress = self.engine.get_progress()
        container_width = self.winfo_width()
        if container_width > 0:
            bar_width = int(container_width * (progress['percentage'] / 100))
            self.progress_bar_fill.configure(width=max(bar_width, 0))
        else:
            self.after(50, self._update_progress_bar_width)

    def submit_answer(self):
        if not self.selected_answers:
            messagebox.showwarning("提示", "请先选择一个答案！")
            return

        answer_str = ''.join(sorted(self.selected_answers))
        result = self.engine.submit_answer(answer_str)
        self.is_answered = True

        if result['is_correct']:
            self.result_label.configure(text="回答正确", fg=GREEN)
        else:
            self.result_label.configure(
                text=f"回答错误，正确答案: {result['correct_answer']}", fg=RED)

            question = self.engine.get_current_question()
            if question.get('number') not in self.progress.get('wrong_questions', []):
                self.progress.setdefault('wrong_questions', []).append(question.get('number'))
                self._save_progress_delayed()

        question = self.engine.get_current_question()
        explanation = question.get('explanation', '暂无解析')
        if not explanation or len(explanation) < 5:
            explanation = '暂无详细解析'

        self.explanation_text.config(state=tk.NORMAL)
        self.explanation_text.delete(1.0, tk.END)
        self.explanation_text.insert(tk.END, explanation)
        self.explanation_text.config(state=tk.DISABLED)

        correct_answer = question.get('answer', '')
        selected_set = set(self.selected_answers)
        correct_set = set(correct_answer)

        for i, card in enumerate(self.option_cards):
            letter = chr(ord('A') + i)
            is_in_correct = letter in correct_set
            is_in_selected = letter in selected_set

            if is_in_correct or is_in_selected:
                card.set_result(is_in_correct, is_in_selected)

        self.submit_btn.configure(state=tk.DISABLED, bg=BTN_DISABLED, text="已提交")

        stats = self.engine.stats
        accuracy = (stats['correct'] / stats['total'] * 100) if stats['total'] > 0 else 0
        self.stats_label.configure(
            text=f"正确 {stats['correct']}  |  错误 {stats['wrong']}  |  正确率 {accuracy:.0f}%")

        self.progress['practice_stats'] = {
            'correct': self.progress.get('practice_stats', {}).get('correct', 0) + (1 if result['is_correct'] else 0),
            'wrong': self.progress.get('practice_stats', {}).get('wrong', 0) + (0 if result['is_correct'] else 1),
            'total': self.progress.get('practice_stats', {}).get('total', 0) + 1
        }
        self._save_progress_delayed()

    def _save_progress_delayed(self):
        self._cancel_all_after_jobs()
        job_id = self.after(2000, self._do_save_progress)
        self._add_after_job(job_id)

    def _do_save_progress(self):
        self.data_manager.save_progress(self.progress)

    def _on_question_resize(self, event=None):
        self.update_idletasks()
        container_width = self.question_label.winfo_width()
        if container_width > 0:
            self.question_label.configure(wraplength=container_width - 10)

    def next_question(self):
        if self.engine.has_next():
            self.engine.next_question()
            self.load_current_question()
        else:
            messagebox.showinfo("提示", "已经是最后一题了！")

    def prev_question(self):
        if self.engine.has_prev():
            self.engine.prev_question()
            self.load_current_question()
        else:
            messagebox.showinfo("提示", "已经是第一题了！")
