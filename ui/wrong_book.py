import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any

from .theme import theme, font_ui, font_ui_semibold, create_primary_button, create_normal_button, create_card

from quiz_engine import QuizEngine
from models import Question
from data_manager import DataManager
from .base_mode import BaseMode
from .practice_session import PracticeSession
from .practice_panel import PracticePanel
from .question_detail_card import QuestionDetailCard
from .mode_toolbar import ModeToolbar


class WrongBook(BaseMode):
    def __init__(
        self,
        parent,
        questions: list[Question],
        data_manager: DataManager | None,
        progress: Any | None,
    ) -> None:
        super().__init__(parent, questions, data_manager, progress)

        self.wrong_questions = self._get_wrong_questions_list()
        # P1-8: 题号→题目索引，O(1) 查找替代线性扫描
        self._wrong_by_number: dict[int, Question] = {q.number: q for q in self.wrong_questions}
        self.practice_engine: QuizEngine | None = None
        self._practice_window: tk.Toplevel | None = None
        self._practice_session: PracticeSession | None = None
        self._practice_panel: PracticePanel | None = None
        # P1-8: 详情对话框懒加载 + 复用（withdraw/deiconify 替代 destroy/create）
        self._detail_dialog: tk.Toplevel | None = None
        self._detail_card: QuestionDetailCard | None = None
        self._detail_header_label: tk.Label | None = None
        self._current_detail_q_num: int | None = None
        # P2-PERF: 题号→Treeview item id，支持增量删除避免全量重建
        self._tree_item_by_number: dict[int, str] = {}

        self._setup_mode_ui()

    def destroy(self) -> None:
        """切 tab 销毁 WrongBook 时，主动关闭所有子窗口，
        避免幽灵窗口持有 engine 引用造成状态分裂。"""
        # P1-8: 清理懒加载的详情对话框
        if self._detail_dialog is not None:
            try:
                self._detail_dialog.grab_release()
                self._detail_dialog.destroy()
            except tk.TclError:
                pass
            self._detail_dialog = None
            self._detail_card = None
            self._detail_header_label = None

        if self._practice_window is not None:
            try:
                self._practice_window.grab_release()
                self._practice_window.destroy()
            except tk.TclError:
                pass
            self._practice_window = None
        super().destroy()

    def _get_wrong_questions_list(self) -> list[Question]:
        wrong_nums = set(self.app_state.get_wrong_questions())
        return [q for q in self.questions if q.number in wrong_nums]

    def _setup_mode_ui(self):
        self.configure(style="TFrame")

        toolbar = ModeToolbar(self)

        self.count_label = tk.Label(
            toolbar.left,
            text=f"共 {len(self.wrong_questions)} 道错题",
            font=font_ui(11),
            fg=theme.RED,
            bg=theme.BG_PAGE,
        )
        self.count_label.pack(side=tk.LEFT)

        practice_btn = create_primary_button(
            toolbar.right,
            text="练习错题",
            command=self.start_practice_wrong,
            padx=16,
            pady=5,
        )
        practice_btn.pack(side=tk.LEFT, padx=(0, 8))

        clear_btn = create_normal_button(
            toolbar.right,
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
        """全量重建 Treeview（初始化/清空时使用）。"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._tree_item_by_number.clear()

        for q in self.wrong_questions:
            content = q.content
            if len(content) > 60:
                content = content[:60] + "..."
            item_id = self.tree.insert("", tk.END, values=(q.number, content, q.answer or "?"))
            self._tree_item_by_number[q.number] = item_id

        self._update_empty_state()

    def _remove_tree_items(self, q_nums: set[int]) -> None:
        """增量删除指定题号对应的 Treeview 行（避免全量重建）。

        若 Treeview 尚未初始化（如测试中直接构造对象），回退到全量重建。
        """
        if not hasattr(self, "_tree_item_by_number") or not self._tree_item_by_number:
            self._populate_tree()
            return

        for q_num in q_nums:
            item_id = self._tree_item_by_number.pop(q_num, None)
            if item_id is not None:
                try:
                    self.tree.delete(item_id)
                except tk.TclError:
                    pass

    def _sync_tree_after_change(self) -> None:
        """状态变更后同步 Treeview、索引和计数标签。"""
        self.wrong_questions = self._get_wrong_questions_list()
        self._wrong_by_number = {q.number: q for q in self.wrong_questions}
        self.count_label.configure(text=f"共 {len(self.wrong_questions)} 道错题")

    def _update_empty_state(self):
        """错题为空时显示空状态视图，否则显示题目列表。"""
        if not hasattr(self, "list_inner"):
            return
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
        # P2-5: Treeview values 跨平台类型不一致（Windows str, macOS/Linux int），
        # 显式转换为 int，避免 _wrong_by_number.get(q_num) 类型不匹配返回 None
        try:
            q_num = int(item["values"][0])
        except (ValueError, IndexError, TypeError):
            return

        # P1-8: O(1) dict 查找替代线性扫描
        question = self._wrong_by_number.get(q_num)
        if not question:
            return

        self._current_detail_q_num = q_num
        self._ensure_detail_dialog()  # 懒加载创建（仅首次）

        # _ensure_detail_dialog 保证以下三个属性已初始化
        assert self._detail_dialog is not None
        assert self._detail_card is not None
        assert self._detail_header_label is not None

        # 复用已有对话框：更新标题 + 内容 + 显示
        self._detail_dialog.title(f"第{q_num}题")
        self._detail_header_label.configure(text=f"第 {q_num} 题")
        self._detail_card.show_question(question, reveal_answer=True)

        self._detail_dialog.deiconify()
        self._detail_dialog.grab_set()
        # 提到最前，确保不被父窗口遮挡
        self._detail_dialog.lift()

    def _ensure_detail_dialog(self) -> None:
        """懒加载创建详情对话框（仅创建一次，后续 withdraw/deiconify 复用）。

        P1-8: 避免每次双击都新建 Toplevel + QuestionDetailCard 的创建开销。
        """
        if self._detail_dialog is not None:
            return

        detail_window = tk.Toplevel(self)
        detail_window.title("题目详情")
        detail_window.geometry("600x500")
        detail_window.configure(bg=theme.BG_PAGE)
        detail_window.transient(self.winfo_toplevel())
        detail_window.protocol("WM_DELETE_WINDOW", self._close_detail_dialog)

        detail_window.update_idletasks()
        width = detail_window.winfo_width()
        height = detail_window.winfo_height()
        x = (detail_window.winfo_screenwidth() // 2) - (width // 2)
        y = (detail_window.winfo_screenheight() // 2) - (height // 2)
        detail_window.geometry(f"{width}x{height}+{x}+{y}")

        header, h_inner = create_card(detail_window, inner_padx=20, inner_pady=14)
        header.pack(fill=tk.X, padx=20, pady=(20, 0))

        self._detail_header_label = tk.Label(
            h_inner,
            text="",
            font=font_ui_semibold(14),
            fg=theme.TEXT_PRIMARY,
            bg=theme.BG_CARD,
        )
        self._detail_header_label.pack(anchor=tk.W)

        self._detail_card = QuestionDetailCard(
            detail_window,
            on_option_click=None,
            option_wraplength=480,
            answer_placeholder="正确答案:",
            inner_padx=20,
            question_inner_pady=14,
            option_inner_pady=14,
            option_pady=2,
        )
        self._detail_card.pack(fill=tk.BOTH, expand=True, padx=20, pady=12)

        btn_frame = tk.Frame(detail_window, bg=theme.BG_PAGE)
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

        master_btn = create_primary_button(
            btn_frame,
            text="标记为已掌握",
            command=self._mark_as_mastered,
            bg_color=theme.GREEN,
            active_bg="#16a34a",
        )
        master_btn.pack(side=tk.LEFT)

        close_btn = create_normal_button(
            btn_frame,
            text="关闭",
            command=self._close_detail_dialog,
        )
        close_btn.pack(side=tk.RIGHT)

        self._detail_dialog = detail_window
        detail_window.withdraw()  # 初始隐藏，等 show_question 后再 deiconify

    def _close_detail_dialog(self) -> None:
        """隐藏详情对话框（复用实例，不销毁）。"""
        if self._detail_dialog is None:
            return
        try:
            self._detail_dialog.grab_release()
            self._detail_dialog.withdraw()
        except tk.TclError:
            pass

    def _mark_as_mastered(self) -> None:
        """标记当前详情对话框显示的题目为已掌握，从错题本移除。"""
        if self._current_detail_q_num is None:
            return
        q_num = self._current_detail_q_num
        if self.app_state.is_wrong_question(q_num):
            self.app_state.remove_wrong_question(q_num)
            # P2-4: 统一用 save_safe 提示保存失败
            save_ok = self.app_state.save_safe()

            # P2-PERF: 增量删除该题，避免全量重建 Treeview
            self._remove_tree_items({q_num})
            self._sync_tree_after_change()
            self._update_empty_state()

            self._close_detail_dialog()
            if save_ok:
                messagebox.showinfo("成功", "该题已从错题本移除！")
            else:
                messagebox.showwarning(
                    "保存失败",
                    "错题本保存失败，请检查磁盘空间或文件权限。",
                    parent=self,
                )

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
        practice_window.minsize(700, 500)
        practice_window.configure(bg=theme.BG_PAGE)
        practice_window.transient(self.winfo_toplevel())
        practice_window.grab_set()
        # P2-UX: 关闭练习窗口前确认，避免误操作丢失当前练习进度
        practice_window.protocol("WM_DELETE_WINDOW", self._on_practice_window_close)

        self._practice_window = practice_window
        self._practice_panel = PracticePanel(
            practice_window,
            session=self._practice_session,
            on_finish=self._show_practice_result,
            on_submit=practice_window.focus_set,
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
        # P2-12: 入口同时校验 _practice_session，避免 lambda 内访问
        # self._practice_session.is_answered 时因 session 为 None 抛 AttributeError
        if not self._practice_panel or not self.practice_engine or not self._practice_session:
            return

        result = self._handle_option_key_press(
            event,
            on_select=self._practice_panel.handle_option_click,
            on_submit=self._practice_panel.submit_answer,
            is_answered_check=lambda: self._practice_session.is_answered,
            engine=self.practice_engine,
        )

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
            # P2-13: correct_nums 转 set，避免 O(N*M) 的线性查找
            correct_nums = set(self._practice_session.get_correct_question_numbers())
            self.app_state.set_wrong_questions(
                [
                    q_num
                    for q_num in self.app_state.get_wrong_questions()
                    if q_num not in correct_nums
                ]
            )

            # P2-4: 统一用 save_safe 提示保存失败
            if not self.app_state.save_safe():
                messagebox.showwarning(
                    "保存失败",
                    "错题本保存失败，请检查磁盘空间或文件权限。",
                    parent=self,
                )
            # P2-PERF: 增量删除答对的题目，避免全量重建 Treeview
            self._remove_tree_items(correct_nums)
            self._sync_tree_after_change()
            self._update_empty_state()

        self._close_practice_window()

    def _on_practice_window_close(self) -> None:
        """用户点击窗口关闭按钮时的确认处理。"""
        if self._practice_window is None or not self._practice_window.winfo_exists():
            self._close_practice_window()
            return

        if messagebox.askyesno(
            "确认关闭",
            "关闭后将结束本次错题练习，是否继续？",
            parent=self._practice_window,
        ):
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
            # P2-4: 统一用 save_safe 提示保存失败
            if not self.app_state.save_safe():
                messagebox.showwarning(
                    "保存失败",
                    "错题本保存失败，请检查磁盘空间或文件权限。",
                    parent=self,
                )

            self.wrong_questions = []
            self._wrong_by_number = {}
            self._tree_item_by_number.clear()
            self._populate_tree()
            self.count_label.configure(text="共 0 道错题")
