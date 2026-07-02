import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Dict, Any, Optional

from .theme import Theme, font_ui, font_ui_semibold, create_primary_button, create_normal_button, create_card

from quiz_engine import QuizEngine
from models import Question
from .base_mode import BaseMode
from .option_row import OptionRow
from .practice_session import PracticeSession
from .practice_panel import PracticePanel

theme = Theme()


class WrongBook(BaseMode):
    def __init__(
        self, parent, questions: List[Question], data_manager, progress: Any
    ) -> None:
        super().__init__(parent, questions, data_manager, progress)

        self.wrong_questions = self._get_wrong_questions_list()
        self.practice_engine: Optional[QuizEngine] = None
        self._practice_window: Optional[tk.Toplevel] = None
        self._detail_windows: List[tk.Toplevel] = []
        self._practice_session: Optional[PracticeSession] = None
        self._practice_panel: Optional[PracticePanel] = None

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

    def _get_wrong_questions_list(self) -> List[Question]:
        wrong_nums = set(self.app_state.get_wrong_questions())
        return [q for q in self.questions if q.number in wrong_nums]

    def _setup_mode_ui(self):
        self.configure(style="TFrame")

        toolbar = tk.Frame(self, bg=theme.BG_PAGE)
        toolbar.pack(fill=tk.X, pady=(0, 12))

        toolbar_left = tk.Frame(toolbar, bg=theme.BG_PAGE)
        toolbar_left.pack(side=tk.LEFT)

        self.count_label = tk.Label(
            toolbar_left,
            text=f"共 {len(self.wrong_questions)} 道错题",
            font=font_ui(11),
            fg=theme.RED,
            bg=theme.BG_PAGE,
        )
        self.count_label.pack(side=tk.LEFT)

        toolbar_right = tk.Frame(toolbar, bg=theme.BG_PAGE)
        toolbar_right.pack(side=tk.RIGHT)

        practice_btn = create_primary_button(
            toolbar_right,
            text="练习错题",
            command=self.start_practice_wrong,
            padx=16,
            pady=5,
        )
        practice_btn.pack(side=tk.LEFT, padx=(0, 8))

        clear_btn = create_normal_button(
            toolbar_right,
            text="清空",
            command=self.clear_all_wrong,
            pady=4,
        )
        clear_btn.pack(side=tk.LEFT)

        list_card = tk.Frame(
            self, bg=theme.BG_CARD, highlightbackground=theme.BORDER, highlightthickness=1
        )
        list_card.pack(fill=tk.BOTH, expand=True)

        self.list_inner = tk.Frame(list_card, bg=theme.BG_CARD)
        self.list_inner.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        style = ttk.Style()
        style.configure(
            "Clean.Treeview",
            background=theme.BG_CARD,
            foreground=theme.TEXT_PRIMARY,
            fieldbackground=theme.BG_CARD,
            font=font_ui(10),
            rowheight=34,
            borderwidth=0,
        )
        style.configure(
            "Clean.Treeview.Heading",
            background=theme.BG_INPUT,
            foreground=theme.TEXT_SECONDARY,
            font=font_ui_semibold(10),
            borderwidth=0,
            relief=tk.FLAT,
        )
        style.map(
            "Clean.Treeview",
            background=[("selected", theme.BG_SELECT)],
            foreground=[("selected", theme.TEXT_PRIMARY)],
        )

        columns = ("number", "content", "answer")
        self.tree = ttk.Treeview(
            self.list_inner, columns=columns, show="headings", height=15, style="Clean.Treeview"
        )

        self.tree.heading("number", text="题号")
        self.tree.heading("content", text="题目内容")
        self.tree.heading("answer", text="正确答案")

        self.tree.column("number", width=70, anchor="center")
        self.tree.column("content", width=600)
        self.tree.column("answer", width=80, anchor="center")

        scrollbar = ttk.Scrollbar(self.list_inner, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 空状态视图（与 list_inner 同级，错题为空时替代 Treeview）
        self.empty_state = tk.Frame(list_card, bg=theme.BG_CARD)
        tk.Label(
            self.empty_state,
            text="还没有错题",
            font=font_ui_semibold(16),
            fg=theme.TEXT_PRIMARY,
            bg=theme.BG_CARD,
        ).pack(pady=(0, 6))
        tk.Label(
            self.empty_state,
            text="继续练习，做错的题会自动收集到这里",
            font=font_ui(11),
            fg=theme.TEXT_MUTED,
            bg=theme.BG_CARD,
        ).pack()

        self._populate_tree()

        self.tree.bind("<Double-1>", self.view_question_detail)

    def _populate_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        for q in self.wrong_questions:
            content = q.content
            if len(content) > 60:
                content = content[:60] + "..."
            self.tree.insert("", tk.END, values=(q.number, content, q.answer or "?"))

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
        q_num = item["values"][0]

        question = next((q for q in self.wrong_questions if q.number == q_num), None)
        if not question:
            return

        detail_window = tk.Toplevel(self)
        detail_window.title(f"第{q_num}题")
        detail_window.geometry("600x500")
        detail_window.configure(bg=theme.BG_PAGE)
        detail_window.transient(self.winfo_toplevel())
        detail_window.grab_set()

        self._detail_windows.append(detail_window)
        detail_window.protocol("WM_DELETE_WINDOW", lambda: self._close_detail_window(detail_window))

        detail_window.update_idletasks()
        width = detail_window.winfo_width()
        height = detail_window.winfo_height()
        x = (detail_window.winfo_screenwidth() // 2) - (width // 2)
        y = (detail_window.winfo_screenheight() // 2) - (height // 2)
        detail_window.geometry(f"{width}x{height}+{x}+{y}")

        header, h_inner = create_card(detail_window, inner_padx=20, inner_pady=14)
        header.pack(fill=tk.X, padx=20, pady=(20, 0))

        tk.Label(
            h_inner,
            text=f"第 {q_num} 题",
            font=font_ui_semibold(14),
            fg=theme.TEXT_PRIMARY,
            bg=theme.BG_CARD,
        ).pack(anchor=tk.W)

        question_card, q_inner = create_card(detail_window, inner_padx=20, inner_pady=14)
        question_card.pack(fill=tk.X, padx=20, pady=12)

        q_text = tk.Text(
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
        q_text.pack(fill=tk.X)
        q_text.insert(tk.END, f"{q_num}. {question.content}")
        q_text.config(state=tk.DISABLED)

        options_card, opt_inner = create_card(detail_window, inner_padx=20, inner_pady=14)
        options_card.pack(fill=tk.X, padx=20, pady=(0, 12))

        for opt in question.options:
            opt_row = tk.Frame(opt_inner, bg=theme.BG_INPUT, padx=10, pady=6)
            opt_row.pack(fill=tk.X, pady=2)

            opt_letter = opt.letter
            is_correct = opt_letter in question.answer

            row_bg = theme.GREEN_BG if is_correct else theme.BG_INPUT
            letter_fg = theme.GREEN_TEXT if is_correct else theme.TEXT_SECONDARY
            text_fg = theme.GREEN_TEXT if is_correct else theme.TEXT_PRIMARY

            opt_row.configure(bg=row_bg)

            tk.Label(
                opt_row,
                text=opt_letter,
                font=font_ui_semibold(11),
                fg=letter_fg,
                bg=row_bg,
                width=2,
                anchor="w",
            ).pack(side=tk.LEFT, padx=(0, 10))

            tk.Label(
                opt_row,
                text=opt.text,
                font=font_ui(11),
                fg=text_fg,
                bg=row_bg,
                wraplength=480,
                justify=tk.LEFT,
                anchor=tk.W,
            ).pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        answer_card, ans_inner = create_card(detail_window, inner_padx=20, inner_pady=14)
        answer_card.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 12))

        ans_top = tk.Frame(ans_inner, bg=theme.BG_CARD)
        ans_top.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            ans_top, text="正确答案:", font=font_ui(11), fg=theme.TEXT_MUTED, bg=theme.BG_CARD
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(
            ans_top,
            text=question.answer or "?",
            font=font_ui_semibold(13),
            fg=theme.GREEN,
            bg=theme.BG_CARD,
        ).pack(side=tk.LEFT)

        exp_container = tk.Frame(ans_inner, bg=theme.BG_CARD)
        exp_container.pack(fill=tk.BOTH, expand=True)

        exp_scrollbar = tk.Scrollbar(exp_container)
        exp_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        exp_text = tk.Text(
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
        exp_text.pack(fill=tk.BOTH, expand=True)
        exp_scrollbar.config(command=exp_text.yview)
        exp_text.insert(tk.END, question.explanation or "暂无解析")
        exp_text.config(state=tk.DISABLED)

        btn_frame = tk.Frame(detail_window, bg=theme.BG_PAGE)
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

        master_btn = create_primary_button(
            btn_frame,
            text="标记为已掌握",
            command=lambda: self._mark_as_mastered(q_num, detail_window),
            bg_color=theme.GREEN,
            active_bg="#16a34a",
        )
        master_btn.pack(side=tk.LEFT)

        close_btn = create_normal_button(
            btn_frame,
            text="关闭",
            command=lambda: self._close_detail_window(detail_window),
        )
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
        if self.app_state.is_wrong_question(q_num):
            self.app_state.remove_wrong_question(q_num)
            self.app_state.save()

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

        # 使用 PracticeSession 管理练习逻辑
        self._practice_session = PracticeSession(self.practice_engine, self.app_state)
        self._practice_session.reset_session(shuffle=True)

        practice_window = tk.Toplevel(self)
        practice_window.title("错题专项练习")
        practice_window.geometry("850x700")
        practice_window.configure(bg=theme.BG_PAGE)
        practice_window.transient(self.winfo_toplevel())
        practice_window.grab_set()

        self._practice_window = practice_window
        self._practice_panel = PracticePanel(
            practice_window,
            session=self._practice_session,
            on_finish=self._show_practice_result,
            show_progress_bar=False,
            show_prev_button=False,
        )
        self._practice_panel.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        self._bind_practice_keyboard(practice_window)
        self._practice_panel.load_current_question()

    def _bind_practice_keyboard(self, window):
        """绑定错题练习窗口的键盘事件。"""
        window.focus_set()
        window.bind("<Key>", self._on_practice_key_press)
        window.bind("<Button-1>", self._on_practice_global_click)

    def _on_practice_global_click(self, event):
        """全局点击设置焦点到练习窗口。"""
        if self._practice_window is not None and self._practice_window.winfo_exists():
            self._practice_window.focus_set()

    def _on_practice_key_press(self, event):
        """错题练习键盘事件处理 - 复用 PracticePanel 的键盘处理。"""
        if not self._practice_panel:
            return

        # 选项键与提交交给面板；面板内部不处理选项键，因此这里先走基类通用方法。
        # 由于基类方法依赖 self.engine，而 WrongBook 的 engine 为 None，临时切换。
        original_engine = self.engine
        self.engine = self.practice_engine

        result = self._handle_option_key_press(
            event,
            on_select=self._practice_panel.handle_option_click,
            on_submit=self._practice_panel.submit_answer,
            is_answered_check=lambda: self._practice_session.is_answered,
        )

        self.engine = original_engine

        if result == "break":
            return "break"

        # 方向键导航交给面板
        return self._practice_panel.handle_key_press(event)

    def _show_practice_result(self):
        if not self._practice_session:
            return

        stats = self._practice_session.get_stats()
        total = stats["total"]
        correct = stats["correct"]
        accuracy = (correct / total * 100) if total > 0 else 0

        msg = f"练习完成！\n\n总题数: {total} 题\n正确: {correct} 题\n错误: {stats['wrong']} 题\n正确率: {accuracy:.1f}%"

        # P1-4: 无论正确率多少，都只询问移除"本次答对"的错题，
        # 从不自动清空全部错题，避免一次性丢失还需复习的题目。
        if messagebox.askyesno(
            "练习完成", msg + "\n\n是否将本次答对的错题从错题本中移除？（答错的仍会保留）"
        ):
            correct_nums = self._practice_session.get_correct_question_numbers()
            self.app_state.set_wrong_questions(
                [
                    q_num
                    for q_num in self.app_state.get_wrong_questions()
                    if q_num not in correct_nums
                ]
            )

            self.app_state.save()
            self.wrong_questions = self._get_wrong_questions_list()
            self._populate_tree()
            self.count_label.configure(text=f"共 {len(self.wrong_questions)} 道错题")

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
        self._practice_session = None

    def clear_all_wrong(self) -> None:
        if not self.wrong_questions:
            messagebox.showinfo("提示", "错题本已经是空的了！")
            return

        if messagebox.askyesno("确认", "确定要清空所有错题吗？此操作不可恢复！"):
            self.app_state.set_wrong_questions([])
            self.app_state.save()

            self.wrong_questions = []
            self._populate_tree()
            self.count_label.configure(text="共 0 道错题")
            messagebox.showinfo("成功", "错题本已清空！")
