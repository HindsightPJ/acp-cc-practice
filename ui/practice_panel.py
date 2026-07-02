"""PracticePanel - 可复用的练习视图组件。

P2: 将 PracticeMode 与 WrongBook 错题练习中重复的练习视图抽离为统一组件，
降低视图层重复代码，同时保持两种使用场景的差异化配置能力。
"""

import tkinter as tk
from tkinter import messagebox
from typing import Any, Callable, Optional

from .theme import Theme, font_ui, font_ui_semibold, create_primary_button, create_normal_button, create_card
from .option_row import OptionRow
from .practice_session import PracticeSession

theme = Theme()


class PracticePanel(tk.Frame):
    """可复用的练习视图组件。

    内部托管 PracticeSession，负责渲染题干、选项、操作栏、结果与解析。
    使用方只需提供会话对象并调用 load_current_question / submit_answer 等接口。

    Args:
        parent: 父容器
        session: 练习会话逻辑对象
        on_finish: 题目队列完成后的回调（可选）
        show_explanation: 是否显示解析文本框（默认 True）
        show_progress_bar: 是否显示顶部进度条（默认 True）
        show_prev_button: 是否显示「上一题」按钮（默认 True）
        show_type_label: 是否显示题型标签（默认 True）
        question_height: 题干文本框高度（默认 4）
    """

    def __init__(
        self,
        parent,
        session: PracticeSession,
        on_finish: Optional[Callable[[], None]] = None,
        show_explanation: bool = True,
        show_progress_bar: bool = True,
        show_prev_button: bool = True,
        show_type_label: bool = True,
        question_height: int = 4,
    ) -> None:
        super().__init__(parent, bg=theme.BG_PAGE)
        self.session = session
        self.on_finish = on_finish
        self.show_explanation = show_explanation
        self.show_progress_bar = show_progress_bar
        self.show_prev_button = show_prev_button
        self.show_type_label = show_type_label
        self.question_height = question_height

        self.option_cards: list[OptionRow] = []
        self._pending_save = False

        self._build_ui()

    def _build_ui(self) -> None:
        """构建练习视图 UI。"""
        # 顶部工具栏
        toolbar = tk.Frame(self, bg=theme.BG_PAGE)
        toolbar.pack(fill=tk.X, pady=(0, 12))

        self.progress_label = tk.Label(
            toolbar,
            text="第 0 / 0 题",
            font=font_ui(11),
            fg=theme.TEXT_SECONDARY,
            bg=theme.BG_PAGE,
        )
        self.progress_label.pack(side=tk.LEFT)

        if self.show_type_label:
            self.type_label = tk.Label(
                toolbar,
                text="",
                font=font_ui_semibold(11),
                bg=theme.BG_PAGE,
            )
            self.type_label.pack(side=tk.RIGHT)
        else:
            self.type_label = None

        # 进度条
        if self.show_progress_bar:
            progress_bg = tk.Frame(self, bg=theme.BORDER, height=3)
            progress_bg.pack(fill=tk.X, pady=(0, 16))
            progress_bg.pack_propagate(False)
            self.progress_bar_fill = tk.Frame(progress_bg, bg=theme.ACCENT, width=0, height=3)
            self.progress_bar_fill.place(x=0, y=0, relheight=1.0)
            self.progress_value = tk.DoubleVar(value=0)
        else:
            self.progress_bar_fill = None
            self.progress_value = None

        # 题干卡片
        question_card, q_inner = create_card(self, inner_pady=16)
        question_card.pack(fill=tk.X, pady=(0, 12))

        self.question_text = tk.Text(
            q_inner,
            height=self.question_height,
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
        self.question_text.pack(fill=tk.X)
        self.question_text.config(state=tk.DISABLED)

        # 选项卡片
        options_card, opt_inner = create_card(self, inner_pady=14)
        options_card.pack(fill=tk.X, pady=(0, 12))

        for idx in range(6):
            letter = chr(ord("A") + idx)
            card = OptionRow(opt_inner, letter=letter, on_click=self.handle_option_click)
            card.pack(fill=tk.X, pady=4)
            self.option_cards.append(card)

        # 操作栏
        action_bar = tk.Frame(self, bg=theme.BG_PAGE)
        action_bar.pack(fill=tk.X, pady=(0, 12))

        btn_left = tk.Frame(action_bar, bg=theme.BG_PAGE)
        btn_left.pack(side=tk.LEFT)

        self.submit_btn = create_primary_button(
            btn_left,
            text="提交答案 (Enter)",
            command=self.submit_answer,
            width=14,
        )
        self.submit_btn.pack(side=tk.LEFT, padx=(0, 8))

        if self.show_prev_button:
            prev_btn = create_normal_button(
                btn_left,
                text="上一题 (←)",
                command=self.prev_question,
            )
            prev_btn.pack(side=tk.LEFT, padx=(0, 4))

        next_btn = create_normal_button(
            btn_left,
            text="下一题 (→)",
            command=self.next_question,
        )
        next_btn.pack(side=tk.LEFT)

        stats_right = tk.Frame(action_bar, bg=theme.BG_PAGE)
        stats_right.pack(side=tk.RIGHT)

        self.stats_label = tk.Label(
            stats_right,
            text="正确 0  |  错误 0  |  正确率 0%",
            font=font_ui_semibold(11),
            fg=theme.ACCENT,
            bg=theme.BG_PAGE,
        )
        self.stats_label.pack()

        # 结果与解析卡片
        result_card, res_inner = create_card(self, inner_pady=14)
        result_card.pack(fill=tk.BOTH, expand=True)

        self.result_label = tk.Label(
            res_inner,
            text="提交答案后查看解析",
            font=font_ui(11),
            fg=theme.TEXT_MUTED,
            bg=theme.BG_CARD,
        )
        self.result_label.pack(anchor=tk.W, pady=(0, 8))

        if self.show_explanation:
            exp_container = tk.Frame(res_inner, bg=theme.BG_CARD)
            exp_container.pack(fill=tk.BOTH, expand=True)

            exp_scrollbar = tk.Scrollbar(exp_container)
            exp_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            self.explanation_text = tk.Text(
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
            self.explanation_text.pack(fill=tk.BOTH, expand=True)
            exp_scrollbar.config(command=self.explanation_text.yview)
            self.explanation_text.config(state=tk.DISABLED)
        else:
            self.explanation_text = None

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def load_current_question(self) -> None:
        """加载当前题目并更新视图。"""
        question = self.session.load_current_question()
        if not question:
            if self.on_finish:
                self.on_finish()
            else:
                messagebox.showinfo("提示", "已完成所有题目！")
            return

        self.question_text.config(state=tk.NORMAL)
        self.question_text.delete(1.0, tk.END)
        self.question_text.insert(
            tk.END, f"{question.number}. {question.content}"
        )
        self.question_text.config(state=tk.DISABLED)

        if self.type_label is not None:
            if question.type == "multiple":
                self.type_label.configure(text="多选题", fg=theme.YELLOW)
            else:
                self.type_label.configure(text="单选题", fg=theme.ACCENT)

        options_count = len(question.options)
        for i, card in enumerate(self.option_cards):
            if i < options_count:
                card.pack(fill=tk.X, pady=4)
                card.update_text(question.options[i].text)
                card.reset()
            else:
                card.pack_forget()

        self.result_label.configure(text="提交答案后查看解析", fg=theme.TEXT_MUTED)
        if self.explanation_text is not None:
            self.explanation_text.config(state=tk.NORMAL)
            self.explanation_text.delete(1.0, tk.END)
            self.explanation_text.config(state=tk.DISABLED)

        self.session.reset_selection()
        self.submit_btn.configure(state=tk.NORMAL, bg=theme.BTN_PRIMARY, text="提交答案 (Enter)")

        self._update_progress()

    def handle_option_click(self, letter: str) -> None:
        """处理选项点击。"""
        question = self.session.engine.get_current_question()
        if question is None:
            return

        options_count = len(question.options)
        self.session.handle_option_click(letter, options_count)

        card_idx = ord(letter) - ord("A")
        if self.session.current_question_type == "single":
            for i, card in enumerate(self.option_cards):
                if i < options_count:
                    card.set_selected(i == card_idx)
        else:
            self.option_cards[card_idx].set_selected(
                self.session.is_option_selected(letter)
            )

    def submit_answer(self) -> None:
        """提交答案并更新视图。"""
        if not self.session.selected_answers:
            messagebox.showwarning("提示", "请先选择一个答案！")
            return

        question = self.session.engine.get_current_question()
        if question is None:
            return

        result = self.session.submit_answer()
        if result is None:
            return

        if result["is_correct"]:
            self.result_label.configure(text="回答正确", fg=theme.GREEN)
        else:
            self.result_label.configure(
                text=f"回答错误，正确答案: {result['correct_answer']}", fg=theme.RED
            )

        if self.explanation_text is not None:
            explanation = question.explanation or "暂无解析"
            if len(explanation) < 5:
                explanation = "暂无详细解析"
            self.explanation_text.config(state=tk.NORMAL)
            self.explanation_text.delete(1.0, tk.END)
            self.explanation_text.insert(tk.END, explanation)
            self.explanation_text.config(state=tk.DISABLED)

        correct_answer = question.answer
        selected_set = set(self.session.selected_answers)
        correct_set = set(correct_answer)

        for i, card in enumerate(self.option_cards):
            letter = chr(ord("A") + i)
            is_in_correct = letter in correct_set
            is_in_selected = letter in selected_set
            if is_in_correct or is_in_selected:
                card.set_result(is_in_correct, is_in_selected)

        self.submit_btn.configure(state=tk.DISABLED, bg=theme.BTN_DISABLED, text="已提交")
        self._update_stats()

    def next_question(self) -> None:
        """下一题。"""
        if self.session.has_next():
            self.session.next_question()
            self.load_current_question()
        else:
            messagebox.showinfo("提示", "已经是最后一题了！")

    def prev_question(self) -> None:
        """上一题。"""
        if self.session.has_prev():
            self.session.prev_question()
            self.load_current_question()
        else:
            messagebox.showinfo("提示", "已经是第一题了！")

    def reset_session(self, shuffle: bool = False) -> None:
        """重置练习会话。"""
        self.session.reset_session(shuffle=shuffle)
        self.load_current_question()

    # ------------------------------------------------------------------
    # 内部更新
    # ------------------------------------------------------------------

    def _update_progress(self) -> None:
        """更新进度条与进度标签。"""
        progress = self.session.get_progress()
        self.progress_label.configure(
            text=f"第 {progress['current']} 题 / 共 {progress['total']} 题"
        )

        if self.progress_value is not None and self.progress_bar_fill is not None:
            self.progress_value.set(progress["percentage"])
            self.update_idletasks()
            container_width = self.winfo_width()
            if container_width > 0:
                bar_width = int(container_width * (progress["percentage"] / 100))
                self.progress_bar_fill.configure(width=max(bar_width, 0))

        self._update_stats()

    def _update_stats(self) -> None:
        """更新统计标签。"""
        stats = self.session.get_stats()
        accuracy = (stats["correct"] / stats["total"] * 100) if stats["total"] > 0 else 0
        self.stats_label.configure(
            text=f"正确 {stats['correct']}  |  错误 {stats['wrong']}  |  正确率 {accuracy:.0f}%"
        )

    # ------------------------------------------------------------------
    # 键盘支持
    # ------------------------------------------------------------------

    def handle_key_press(self, event) -> Optional[str]:
        """处理键盘事件。

        Returns:
            若已处理并应阻止进一步传播，返回 "break"；否则返回 None。
        """
        # 由使用方提供 _handle_option_key_press 或自行处理；
        # 这里仅处理方向键导航，因为选项键需要与宿主共享基类方法。
        if event.keysym == "Right":
            self.next_question()
            return "break"
        if event.keysym == "Left" and self.show_prev_button:
            self.prev_question()
            return "break"
        return None
