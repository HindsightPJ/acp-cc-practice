import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Dict, Any, Optional

from .theme import (
    BG_PAGE, BG_CARD, BG_INPUT, BG_SELECT,
    BORDER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT,
    GREEN, GREEN_BG, GREEN_BORDER, GREEN_TEXT,
    RED, RED_BG, RED_BORDER, RED_TEXT,
    BTN_PRIMARY, BTN_PRIMARY_HOVER, BTN_PRIMARY_ACTIVE,
    BTN_NORMAL, BTN_NORMAL_FG, BTN_NORMAL_HOVER, BTN_NORMAL_ACTIVE,
    BTN_DISABLED, BTN_DISABLED_FG,
    SELECTED_BG, SELECTED_TEXT,
    CORRECT_BG, CORRECT_TEXT,
    WRONG_BG, WRONG_TEXT,
    font_ui, font_ui_semibold,
)
from quiz_engine import QuizEngine
from .base_mode import BaseMode
from .option_row import OptionRow


class WrongBook(BaseMode):
    def __init__(self, parent, questions: List[Dict[str, Any]],
                 data_manager, progress: Dict[str, Any]) -> None:
        super().__init__(parent, questions, data_manager, progress)

        self.wrong_questions = self._get_wrong_questions_list()
        self.practice_engine = None
        self._practice_window = None
        self._detail_windows = []

        self._setup_mode_ui()

    def destroy(self) -> None:
        """切 tab 销毁 WrongBook 时，主动关闭所有子窗口，
        避免幽灵窗口持有 engine 引用造成状态分裂。"""
        for dw in self._detail_windows:
            try:
                dw.grab_release()
                dw.destroy()
            except tk.TclError:
                pass
        self._detail_windows.clear()

        if self._practice_window is not None:
            try:
                self._practice_window.grab_release()
                self._practice_window.destroy()
            except tk.TclError:
                pass
            self._practice_window = None
        super().destroy()

    def _get_wrong_questions_list(self) -> List[Dict[str, Any]]:
        wrong_nums = set(self.progress.get('wrong_questions', []))
        return [q for q in self.questions if q.get('number') in wrong_nums]

    def _setup_mode_ui(self):
        self.configure(style='TFrame')

        toolbar = tk.Frame(self, bg=BG_PAGE)
        toolbar.pack(fill=tk.X, pady=(0, 12))

        toolbar_left = tk.Frame(toolbar, bg=BG_PAGE)
        toolbar_left.pack(side=tk.LEFT)

        self.count_label = tk.Label(
            toolbar_left, text=f"共 {len(self.wrong_questions)} 道错题",
            font=font_ui(11), fg=RED, bg=BG_PAGE)
        self.count_label.pack(side=tk.LEFT)

        toolbar_right = tk.Frame(toolbar, bg=BG_PAGE)
        toolbar_right.pack(side=tk.RIGHT)

        practice_btn = tk.Button(toolbar_right, text="练习错题",
                                 command=self.start_practice_wrong,
                                 font=font_ui_semibold(11), fg='#ffffff', bg=BTN_PRIMARY,
                                 activebackground=BTN_PRIMARY_ACTIVE,
                                 relief=tk.FLAT, padx=16, pady=5, cursor='hand2')
        practice_btn.pack(side=tk.LEFT, padx=(0, 8))

        clear_btn = tk.Button(toolbar_right, text="清空",
                              command=self.clear_all_wrong,
                              font=font_ui(10), fg=BTN_NORMAL_FG, bg=BTN_NORMAL,
                              activebackground=BTN_NORMAL_HOVER,
                              relief=tk.FLAT, padx=12, pady=4, cursor='hand2')
        clear_btn.pack(side=tk.LEFT)

        list_card = tk.Frame(self, bg=BG_CARD, highlightbackground=BORDER,
                             highlightthickness=1)
        list_card.pack(fill=tk.BOTH, expand=True)

        self.list_inner = tk.Frame(list_card, bg=BG_CARD)
        self.list_inner.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        style = ttk.Style()
        style.configure('Clean.Treeview',
                        background=BG_CARD,
                        foreground=TEXT_PRIMARY,
                        fieldbackground=BG_CARD,
                        font=font_ui(10),
                        rowheight=34,
                        borderwidth=0)
        style.configure('Clean.Treeview.Heading',
                        background=BG_INPUT,
                        foreground=TEXT_SECONDARY,
                        font=font_ui_semibold(10),
                        borderwidth=0,
                        relief=tk.FLAT)
        style.map('Clean.Treeview',
                  background=[('selected', BG_SELECT)],
                  foreground=[('selected', TEXT_PRIMARY)])

        columns = ('number', 'content', 'answer')
        self.tree = ttk.Treeview(self.list_inner, columns=columns,
                                 show='headings', height=15,
                                 style='Clean.Treeview')

        self.tree.heading('number', text='题号')
        self.tree.heading('content', text='题目内容')
        self.tree.heading('answer', text='正确答案')

        self.tree.column('number', width=70, anchor='center')
        self.tree.column('content', width=600)
        self.tree.column('answer', width=80, anchor='center')

        scrollbar = ttk.Scrollbar(self.list_inner, orient=tk.VERTICAL,
                                  command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 空状态视图（与 list_inner 同级，错题为空时替代 Treeview）
        self.empty_state = tk.Frame(list_card, bg=BG_CARD)
        tk.Label(self.empty_state, text="还没有错题",
                 font=font_ui_semibold(16), fg=TEXT_PRIMARY, bg=BG_CARD).pack(pady=(0, 6))
        tk.Label(self.empty_state, text="继续练习，做错的题会自动收集到这里",
                 font=font_ui(11), fg=TEXT_MUTED, bg=BG_CARD).pack()

        self._populate_tree()

        self.tree.bind('<Double-1>', self.view_question_detail)

    def _populate_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        for q in self.wrong_questions:
            content = q.get('content', '')
            if len(content) > 60:
                content = content[:60] + '...'
            self.tree.insert('', tk.END, values=(
                q.get('number'),
                content,
                q.get('answer', '?')
            ))

        self._update_empty_state()

    def _update_empty_state(self):
        """错题为空时显示空状态视图，否则显示题目列表。"""
        if not self.wrong_questions:
            self.list_inner.pack_forget()
            self.empty_state.pack(fill=tk.BOTH, expand=True)
        else:
            self.empty_state.pack_forget()
            self.list_inner.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    def view_question_detail(self, event) -> None:
        selection = self.tree.selection()
        if not selection:
            return

        item = self.tree.item(selection[0])
        q_num = item['values'][0]

        question = next((q for q in self.wrong_questions if q.get('number') == q_num), None)
        if not question:
            return

        detail_window = tk.Toplevel(self)
        detail_window.title(f"第{q_num}题")
        detail_window.geometry("600x500")
        detail_window.configure(bg=BG_PAGE)
        detail_window.transient(self.winfo_toplevel())
        detail_window.grab_set()

        self._detail_windows.append(detail_window)
        detail_window.protocol("WM_DELETE_WINDOW", lambda: self._close_detail_window(detail_window))

        detail_window.update_idletasks()
        width = detail_window.winfo_width()
        height = detail_window.winfo_height()
        x = (detail_window.winfo_screenwidth() // 2) - (width // 2)
        y = (detail_window.winfo_screenheight() // 2) - (height // 2)
        detail_window.geometry(f'{width}x{height}+{x}+{y}')

        header = tk.Frame(detail_window, bg=BG_CARD, highlightbackground=BORDER,
                          highlightthickness=1)
        header.pack(fill=tk.X, padx=20, pady=(20, 0))

        h_inner = tk.Frame(header, bg=BG_CARD)
        h_inner.pack(fill=tk.BOTH, expand=True, padx=20, pady=14)

        tk.Label(h_inner, text=f"第 {q_num} 题",
                 font=font_ui_semibold(14), fg=TEXT_PRIMARY, bg=BG_CARD).pack(anchor=tk.W)

        question_card = tk.Frame(detail_window, bg=BG_CARD, highlightbackground=BORDER,
                                 highlightthickness=1)
        question_card.pack(fill=tk.X, padx=20, pady=12)

        q_inner = tk.Frame(question_card, bg=BG_CARD)
        q_inner.pack(fill=tk.BOTH, expand=True, padx=20, pady=14)

        q_text = tk.Text(q_inner, height=4, wrap=tk.WORD,
                         font=font_ui(12), bg=BG_CARD, fg=TEXT_PRIMARY,
                         relief=tk.FLAT, padx=0, pady=0,
                         selectbackground=BG_SELECT, insertbackground=TEXT_PRIMARY)
        q_text.pack(fill=tk.X)
        q_text.insert(tk.END, f"{q_num}. {question.get('content')}")
        q_text.config(state=tk.DISABLED)

        options_card = tk.Frame(detail_window, bg=BG_CARD, highlightbackground=BORDER,
                                highlightthickness=1)
        options_card.pack(fill=tk.X, padx=20, pady=(0, 12))

        opt_inner = tk.Frame(options_card, bg=BG_CARD)
        opt_inner.pack(fill=tk.BOTH, expand=True, padx=20, pady=14)

        for opt in question.get('options', []):
            opt_row = tk.Frame(opt_inner, bg=BG_INPUT, padx=10, pady=6)
            opt_row.pack(fill=tk.X, pady=2)

            opt_letter = opt.get('letter', '')
            is_correct = opt_letter in question.get('answer', '')

            row_bg = GREEN_BG if is_correct else BG_INPUT
            letter_fg = GREEN_TEXT if is_correct else TEXT_SECONDARY
            text_fg = GREEN_TEXT if is_correct else TEXT_PRIMARY

            opt_row.configure(bg=row_bg)

            tk.Label(opt_row, text=opt_letter,
                     font=font_ui_semibold(11), fg=letter_fg, bg=row_bg,
                     width=2, anchor='w').pack(side=tk.LEFT, padx=(0, 10))

            tk.Label(opt_row, text=opt.get('text', ''),
                     font=font_ui(11), fg=text_fg, bg=row_bg,
                     wraplength=480, justify=tk.LEFT, anchor=tk.W).pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        answer_card = tk.Frame(detail_window, bg=BG_CARD, highlightbackground=BORDER,
                               highlightthickness=1)
        answer_card.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 12))

        ans_inner = tk.Frame(answer_card, bg=BG_CARD)
        ans_inner.pack(fill=tk.BOTH, expand=True, padx=20, pady=14)

        ans_top = tk.Frame(ans_inner, bg=BG_CARD)
        ans_top.pack(fill=tk.X, pady=(0, 8))

        tk.Label(ans_top, text="正确答案:",
                 font=font_ui(11), fg=TEXT_MUTED, bg=BG_CARD).pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(ans_top, text=question.get('answer', '?'),
                 font=font_ui_semibold(13), fg=GREEN, bg=BG_CARD).pack(side=tk.LEFT)

        exp_container = tk.Frame(ans_inner, bg=BG_CARD)
        exp_container.pack(fill=tk.BOTH, expand=True)

        exp_scrollbar = tk.Scrollbar(exp_container)
        exp_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        exp_text = tk.Text(exp_container, wrap=tk.WORD,
                           font=font_ui(11), bg=BG_CARD, fg=TEXT_SECONDARY,
                           relief=tk.FLAT, padx=0, pady=0,
                           yscrollcommand=exp_scrollbar.set,
                           selectbackground=BG_SELECT, insertbackground=TEXT_PRIMARY)
        exp_text.pack(fill=tk.BOTH, expand=True)
        exp_scrollbar.config(command=exp_text.yview)
        exp_text.insert(tk.END, question.get('explanation', '暂无解析'))
        exp_text.config(state=tk.DISABLED)

        btn_frame = tk.Frame(detail_window, bg=BG_PAGE)
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

        master_btn = tk.Button(btn_frame, text="标记为已掌握",
                               command=lambda: self._mark_as_mastered(q_num, detail_window),
                               font=font_ui_semibold(11), fg='#ffffff', bg=GREEN,
                               activebackground='#16a34a',
                               relief=tk.FLAT, padx=16, pady=6, cursor='hand2')
        master_btn.pack(side=tk.LEFT)

        close_btn = tk.Button(btn_frame, text="关闭",
                              command=lambda: self._close_detail_window(detail_window),
                              font=font_ui(10), fg=BTN_NORMAL_FG, bg=BTN_NORMAL,
                              activebackground=BTN_NORMAL_HOVER,
                              relief=tk.FLAT, padx=12, pady=5, cursor='hand2')
        close_btn.pack(side=tk.RIGHT)

    def _close_detail_window(self, window):
        """安全关闭详情窗口并从跟踪列表移除。"""
        try:
            if window in self._detail_windows:
                self._detail_windows.remove(window)
            window.grab_release()
            window.destroy()
        except tk.TclError:
            pass

    def _mark_as_mastered(self, q_num, window):
        if q_num in self.progress.get('wrong_questions', []):
            self.progress['wrong_questions'].remove(q_num)
            self.data_manager.save_progress(self.progress)

            self.wrong_questions = self._get_wrong_questions_list()
            self._populate_tree()
            self.count_label.configure(text=f"共 {len(self.wrong_questions)} 道错题")

            self._close_detail_window(window)
            messagebox.showinfo("成功", "该题已从错题本移除！")

    def start_practice_wrong(self) -> None:
        if not self.wrong_questions:
            messagebox.showinfo("提示", "错题本是空的，继续加油！")
            return

        self.practice_engine = QuizEngine(self.wrong_questions)
        self.practice_engine.start_practice_mode(shuffle=True)

        practice_window = tk.Toplevel(self)
        practice_window.title("错题专项练习")
        practice_window.geometry("850x620")
        practice_window.configure(bg=BG_PAGE)
        practice_window.transient(self.winfo_toplevel())
        practice_window.grab_set()

        self._practice_window = practice_window
        self._setup_practice_ui(practice_window)
        self._bind_practice_keyboard(practice_window)
        self._load_practice_question()

    def _setup_practice_ui(self, parent):
        info_bar = tk.Frame(parent, bg=BG_CARD, highlightbackground=BORDER,
                            highlightthickness=1)
        info_bar.pack(fill=tk.X, padx=20, pady=(20, 0))

        info_inner = tk.Frame(info_bar, bg=BG_CARD)
        info_inner.pack(fill=tk.BOTH, expand=True, padx=20, pady=12)

        self.practice_progress_label = tk.Label(
            info_inner, text="第 0 / 0 题",
            font=font_ui(11), fg=TEXT_SECONDARY, bg=BG_CARD)
        self.practice_progress_label.pack(side=tk.LEFT)

        self.practice_stats_label = tk.Label(
            info_inner, text="正确 0  |  错误 0  |  正确率 0%",
            font=font_ui_semibold(11), fg=ACCENT, bg=BG_CARD)
        self.practice_stats_label.pack(side=tk.RIGHT)

        question_card = tk.Frame(parent, bg=BG_CARD, highlightbackground=BORDER,
                                 highlightthickness=1)
        question_card.pack(fill=tk.X, padx=20, pady=12)

        q_inner = tk.Frame(question_card, bg=BG_CARD)
        q_inner.pack(fill=tk.BOTH, expand=True, padx=20, pady=16)

        self.pq_text = tk.Text(q_inner, height=4, wrap=tk.WORD,
                               font=font_ui(12), bg=BG_CARD, fg=TEXT_PRIMARY,
                               relief=tk.FLAT, padx=0, pady=0,
                               selectbackground=BG_SELECT, insertbackground=TEXT_PRIMARY)
        self.pq_text.pack(fill=tk.X)
        self.pq_text.config(state=tk.DISABLED)

        options_card = tk.Frame(parent, bg=BG_CARD, highlightbackground=BORDER,
                                highlightthickness=1)
        options_card.pack(fill=tk.X, padx=20, pady=(0, 12))

        opt_inner = tk.Frame(options_card, bg=BG_CARD)
        opt_inner.pack(fill=tk.BOTH, expand=True, padx=20, pady=14)

        self.po_buttons = []
        for letter in ['A', 'B', 'C', 'D', 'E', 'F']:
            row = OptionRow(opt_inner, letter=letter,
                            on_click=lambda l: self._practice_on_click(l))
            row.pack(fill=tk.X, pady=2)
            self.po_buttons.append({
                'row': row,
                'var': tk.IntVar(value=0),
                'letter': letter,
            })
            if ord(letter) - ord('A') >= 4:
                row.pack_forget()

        action_bar = tk.Frame(parent, bg=BG_PAGE)
        action_bar.pack(fill=tk.X, padx=20, pady=10)

        self.psubmit_btn = tk.Button(
            action_bar, text="提交答案",
            command=self._psubmit_answer,
            font=font_ui_semibold(11), fg='#ffffff', bg=BTN_PRIMARY,
            activebackground=BTN_PRIMARY_ACTIVE,
            relief=tk.FLAT, width=12, padx=16, pady=6, cursor='hand2')
        self.psubmit_btn.pack(side=tk.LEFT, padx=(0, 8))

        next_btn = tk.Button(action_bar, text="下一题",
                             command=self._pnext_question,
                             font=font_ui(10), fg=BTN_NORMAL_FG, bg=BTN_NORMAL,
                             activebackground=BTN_NORMAL_HOVER,
                             relief=tk.FLAT, padx=12, pady=5, cursor='hand2')
        next_btn.pack(side=tk.LEFT)

        self.presult_label = tk.Label(parent, text="",
                                      font=font_ui(12), fg=TEXT_PRIMARY, bg=BG_PAGE)
        self.presult_label.pack(pady=10)

        self.panswered = False

    def _bind_practice_keyboard(self, window):
        """绑定错题练习窗口的键盘事件"""
        window.focus_set()
        window.bind('<Key>', self._on_practice_key_press)
        window.bind('<Button-1>', self._on_practice_global_click)

    def _on_practice_global_click(self, event):
        """全局点击设置焦点到练习窗口"""
        if self._practice_window is not None and self._practice_window.winfo_exists():
            self._practice_window.focus_set()

    def _on_practice_key_press(self, event):
        """错题练习键盘事件处理"""
        if not self.practice_engine or not self.practice_engine.get_current_question():
            return

        key = event.char.upper() if event.char else ''
        keysym = event.keysym

        # 字母选择答案 (A-F)
        if key and key in 'ABCDEF' and not self.panswered:
            card_idx = ord(key) - ord('A')
            options_count = len(self.practice_engine.get_current_question().get('options', []))
            if card_idx < options_count:
                self._practice_select_by_index(card_idx)
            return 'break'

        # 数字选择答案 (1-6)
        if key and key in '123456' and not self.panswered:
            card_idx = int(key) - 1
            options_count = len(self.practice_engine.get_current_question().get('options', []))
            if card_idx < options_count:
                self._practice_select_by_index(card_idx)
            return 'break'

        # Enter 提交答案
        if keysym == 'Return' and not self.panswered:
            self._psubmit_answer()
            return 'break'

        # 方向键下一题
        if keysym == 'Right':
            self._pnext_question()
            return 'break'

    def _practice_on_click(self, letter: str) -> None:
        """错题练习选项点击：通过字母定位到对应行后切换状态。"""
        idx = ord(letter) - ord('A')
        if 0 <= idx < len(self.po_buttons):
            self._practice_select_by_index(idx)

    def _practice_select_by_index(self, idx):
        """通过索引选择练习选项"""
        if self.panswered:
            return

        item = self.po_buttons[idx]
        var = item['var']
        row = item['row']

        question = self.practice_engine.get_current_question()
        is_multiple = question.get('type') == 'multiple'

        if is_multiple:
            # 多选题：切换当前选项
            if var.get() == 1:
                var.set(0)
                row.set_selected(False)
            else:
                var.set(1)
                row.set_selected(True)
        else:
            # 单选题：取消其他选项
            for po_item in self.po_buttons:
                if po_item['var'].get() == 1:
                    po_item['var'].set(0)
                    po_item['row'].set_selected(False)

            var.set(1)
            row.set_selected(True)

    def _load_practice_question(self):
        question = self.practice_engine.get_current_question()
        if not question:
            self._show_practice_result()
            return

        self.pq_text.config(state=tk.NORMAL)
        self.pq_text.delete(1.0, tk.END)
        self.pq_text.insert(tk.END, f"{question.get('number')}. {question.get('content')}")
        self.pq_text.config(state=tk.DISABLED)

        options = question.get('options', [])
        for i, item in enumerate(self.po_buttons):
            if i < len(options):
                item['row'].pack(fill=tk.X, pady=2)
                item['row'].update_text(options[i].get('text', ''))
            else:
                item['row'].pack_forget()
            item['var'].set(0)
            item['row'].reset()

        self.presult_label.configure(text="")
        self.psubmit_btn.configure(state=tk.NORMAL, bg=BTN_PRIMARY)
        self.panswered = False

        progress = self.practice_engine.get_progress()
        self.practice_progress_label.configure(
            text=f"第 {progress['current']} / {progress['total']} 题")

        # P2-3: 统一用 get_stats() 显式接口访问统计，与 _psubmit_answer 保持一致。
        stats = self.practice_engine.get_stats()
        accuracy = (stats['correct'] / stats['total'] * 100) if stats['total'] > 0 else 0
        self.practice_stats_label.configure(
            text=f"正确 {stats['correct']}  |  错误 {stats['wrong']}  |  正确率 {accuracy:.0f}%")

    def _psubmit_answer(self):
        selected_letters = []
        for item in self.po_buttons:
            if item['var'].get() == 1:
                selected_letters.append(item['letter'])

        if not selected_letters:
            messagebox.showwarning("提示", "请先选择答案！")
            return

        selected_letters.sort()
        answer_str = ''.join(selected_letters)
        result = self.practice_engine.submit_answer(answer_str)
        self.panswered = True

        # 写回主页练习统计
        ps = self.progress.get('practice_stats', {'correct': 0, 'wrong': 0, 'total': 0})
        ps['total'] = ps.get('total', 0) + 1
        if result['is_correct']:
            ps['correct'] = ps.get('correct', 0) + 1
        else:
            ps['wrong'] = ps.get('wrong', 0) + 1
        self.progress['practice_stats'] = ps
        self.data_manager.save_progress(self.progress)

        if result['is_correct']:
            self.presult_label.configure(text="回答正确", fg=GREEN)
        else:
            self.presult_label.configure(
                text=f"回答错误，正确答案: {result['correct_answer']}", fg=RED)

        question = self.practice_engine.get_current_question()
        correct_answer = question.get('answer', '')
        correct_set = set(correct_answer)
        selected_set = set(selected_letters)
        for item in self.po_buttons:
            letter = item['letter']
            is_in_correct = letter in correct_set
            is_in_selected = letter in selected_set
            if is_in_correct or is_in_selected:
                item['row'].set_result(is_in_correct, is_in_selected)
            else:
                item['row'].reset()

        self.psubmit_btn.configure(state=tk.DISABLED, bg=BTN_DISABLED)

        stats = self.practice_engine.get_stats()
        accuracy = (stats['correct'] / stats['total'] * 100) if stats['total'] > 0 else 0
        self.practice_stats_label.configure(
            text=f"正确 {stats['correct']}  |  错误 {stats['wrong']}  |  正确率 {accuracy:.0f}%")

    def _pnext_question(self):
        if self.practice_engine.has_next():
            self.practice_engine.next_question()
            self._load_practice_question()
        else:
            self._show_practice_result()

    def _show_practice_result(self):
        stats = self.practice_engine.get_stats()
        total = stats['total']
        correct = stats['correct']
        accuracy = (correct / total * 100) if total > 0 else 0

        msg = f"练习完成！\n\n总题数: {total} 题\n正确: {correct} 题\n错误: {stats['wrong']} 题\n正确率: {accuracy:.1f}%"

        if accuracy >= 80:
            msg += "\n\n太棒了！你已经掌握了这些错题！"
            # P1-4: 只移除本次练习中答对的错题，而非全部错题。
            # 此前遍历 self.wrong_questions 全部移除，包括答错的 20%。
            if messagebox.askyesno("恭喜", msg + "\n\n是否将本次答对的错题从错题本中移除？"):
                correct_nums = self.practice_engine.get_correct_question_numbers()
                self.progress['wrong_questions'] = [
                    q_num for q_num in self.progress.get('wrong_questions', [])
                    if q_num not in correct_nums
                ]

                self.data_manager.save_progress(self.progress)
                self.wrong_questions = self._get_wrong_questions_list()
                self._populate_tree()
                self.count_label.configure(text=f"共 {len(self.wrong_questions)} 道错题")
        else:
            messagebox.showinfo("练习完成", msg + "\n\n继续努力，多复习几遍吧！")

        self._close_practice_window()

    def _close_practice_window(self):
        """关闭错题练习子窗口。"""
        if self._practice_window is not None:
            try:
                self._practice_window.grab_release()
                self._practice_window.destroy()
            except tk.TclError:
                pass
            self._practice_window = None

    def clear_all_wrong(self) -> None:
        if not self.wrong_questions:
            messagebox.showinfo("提示", "错题本已经是空的了！")
            return

        if messagebox.askyesno("确认", "确定要清空所有错题吗？此操作不可恢复！"):
            self.progress['wrong_questions'] = []
            self.data_manager.save_progress(self.progress)

            self.wrong_questions = []
            self._populate_tree()
            self.count_label.configure(text="共 0 道错题")
            messagebox.showinfo("成功", "错题本已清空！")
