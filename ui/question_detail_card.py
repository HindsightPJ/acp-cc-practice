"""QuestionDetailCard - 题目详情卡片统一组件。

将题干、选项、答案/解析三段卡片的渲染逻辑集中，供 WrongBook 详情弹窗、
PracticePanel、ReviewMode 三处复用，消除约 150 行重复样板代码。

设计原则：
- 组件只负责"题目内容渲染"，不关心外壳（Toplevel / Frame）、工具栏、操作栏；
- 调用方通过组合 show_question / reveal_correct_options / set_option_result
  等原子方法实现各自的交互逻辑（只读查看 / 答题反馈 / 显隐切换）。
"""

import tkinter as tk
from typing import Callable

from .theme import theme, font_ui, create_card
from .option_row import OptionRow
from models import Question


class QuestionDetailCard(tk.Frame):
    """题目详情卡片组件。

    三段式结构：题干卡 + 选项卡 + 答案/解析卡。卡片之间的垂直间距由组件
    内部统一为 12px；水平外边距由调用方通过 pack(padx=...) 控制。

    Args:
        parent: 父容器
        on_option_click: 选项点击回调 (letter: str) -> None；None 表示只读
        question_height: 题干文本框高度（行数）
        option_wraplength: 选项文字换行宽度
        show_explanation: 是否构建解析文本框
        answer_placeholder: 答案标签初始文本（如 "提交答案后查看解析"）
        inner_padx: 卡片内层水平内边距
        question_inner_pady: 题干卡内层垂直内边距
        option_inner_pady: 选项卡 / 答案卡内层垂直内边距
        option_pady: 选项行之间的垂直间距
        insert_action_bar: 在选项卡之后、答案卡之前调用，调用方负责 pack 自定义操作栏；
            签名 (container: tk.Frame) -> None。用于 PracticePanel 的"操作栏在中间"布局
    """

    def __init__(
        self,
        parent,
        on_option_click: Callable[[str], None] | None = None,
        question_height: int = 4,
        option_wraplength: int = 700,
        show_explanation: bool = True,
        answer_placeholder: str = "",
        inner_padx: int = 20,
        question_inner_pady: int = 16,
        option_inner_pady: int = 14,
        option_pady: int = 2,
        insert_action_bar: Callable[[tk.Frame], None] | None = None,
    ) -> None:
        super().__init__(parent, bg=theme.BG_PAGE)
        self._on_option_click = on_option_click
        self._question_height = question_height
        self._option_wraplength = option_wraplength
        self._show_explanation = show_explanation
        self._answer_placeholder = answer_placeholder
        self._inner_padx = inner_padx
        self._question_inner_pady = question_inner_pady
        self._option_inner_pady = option_inner_pady
        self._option_pady = option_pady
        self._insert_action_bar = insert_action_bar

        self.option_cards: list[OptionRow] = []
        self.question_text: tk.Text | None = None
        self.answer_label: tk.Label | None = None
        self.explanation_text: tk.Text | None = None

        self._build_ui()

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # 题干卡
        question_card, q_inner = create_card(
            self, inner_padx=self._inner_padx, inner_pady=self._question_inner_pady
        )
        question_card.pack(fill=tk.X, pady=(0, 12))

        self.question_text = tk.Text(
            q_inner,
            height=self._question_height,
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

        # 选项卡
        options_card, opt_inner = create_card(
            self, inner_padx=self._inner_padx, inner_pady=self._option_inner_pady
        )
        options_card.pack(fill=tk.X, pady=(0, 12))

        for idx in range(6):
            letter = chr(ord("A") + idx)
            card = OptionRow(
                opt_inner,
                letter=letter,
                on_click=self._on_option_click,
                wraplength=self._option_wraplength,
            )
            card.pack(fill=tk.X, pady=self._option_pady)
            self.option_cards.append(card)

        # 调用方插入操作栏（如 PracticePanel 的"提交/上一题/下一题"按钮组）
        if self._insert_action_bar is not None:
            self._insert_action_bar(self)

        # 答案 / 解析卡
        answer_card, ans_inner = create_card(
            self, inner_padx=self._inner_padx, inner_pady=self._option_inner_pady
        )
        answer_card.pack(fill=tk.BOTH, expand=True)

        ans_top = tk.Frame(ans_inner, bg=theme.BG_CARD)
        ans_top.pack(fill=tk.X, pady=(0, 8))

        self.answer_label = tk.Label(
            ans_top,
            text=self._answer_placeholder,
            font=font_ui(11),
            fg=theme.TEXT_MUTED,
            bg=theme.BG_CARD,
        )
        self.answer_label.pack(side=tk.LEFT)

        if self._show_explanation:
            exp_container = tk.Frame(ans_inner, bg=theme.BG_CARD)
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

    # ------------------------------------------------------------------
    # 内容更新
    # ------------------------------------------------------------------

    def show_question(self, question: Question, *, reveal_answer: bool = False) -> None:
        """渲染题干与选项；可选同时高亮正确答案与显示解析。

        Args:
            question: 题目对象
            reveal_answer: True 时同时执行 reveal_correct_options + set_explanation，
                并将答案标签设为 "正确答案: {answer}" 绿色
        """
        if self.question_text is None:
            return

        self._set_text(self.question_text, f"{question.number}. {question.content}")

        options_count = len(question.options)
        for i, card in enumerate(self.option_cards):
            if i < options_count:
                card.pack(fill=tk.X, pady=self._option_pady)
                card.update_text(question.options[i].text)
                card.reset()
            else:
                card.pack_forget()

        if reveal_answer:
            self.reveal_correct_options(question)
            self.set_answer_label(f"正确答案: {question.answer or '未知'}", fg=theme.GREEN)
            self.set_explanation(question.explanation or "暂无解析")
        else:
            self.clear_answer_state()

    def reveal_correct_options(self, question: Question) -> None:
        """高亮正确答案选项，其余选项 reset。仅修改选项状态，不动答案标签/解析。"""
        correct_answer = question.answer or ""
        for i, card in enumerate(self.option_cards):
            letter = chr(ord("A") + i)
            if letter in correct_answer and i < len(question.options):
                card.reveal_correct()
            else:
                card.reset()

    def set_option_result(self, correct_answer: str, selected: str) -> None:
        """提交后标记选项结果态（用于 PracticePanel 答题反馈）。

        Args:
            correct_answer: 正确答案字母串，如 "ABC"
            selected: 用户选中的字母串，如 "AC"
        """
        correct_set = set(correct_answer)
        selected_set = set(selected)
        for i, card in enumerate(self.option_cards):
            letter = chr(ord("A") + i)
            is_correct = letter in correct_set
            is_selected = letter in selected_set
            if is_correct or is_selected:
                card.set_result(is_correct, is_selected)

    def reset_options(self) -> None:
        """重置所有选项状态为 idle。"""
        for card in self.option_cards:
            card.reset()

    def set_answer_label(self, text: str, fg: str = theme.GREEN) -> None:
        """更新答案标签文本与颜色。"""
        if self.answer_label is not None:
            self.answer_label.configure(text=text, fg=fg)

    def clear_answer_state(self) -> None:
        """重置答案标签为占位文本（muted 色），清空解析。"""
        if self.answer_label is not None:
            self.answer_label.configure(text=self._answer_placeholder, fg=theme.TEXT_MUTED)
        self._set_explanation("")

    def set_explanation(self, text: str) -> None:
        """更新解析文本框内容。"""
        self._set_explanation(text)

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _set_text(self, widget: tk.Text, content: str) -> None:
        widget.config(state=tk.NORMAL)
        widget.delete(1.0, tk.END)
        widget.insert(tk.END, content)
        widget.config(state=tk.DISABLED)

    def _set_explanation(self, content: str) -> None:
        if self.explanation_text is None:
            return
        self.explanation_text.config(state=tk.NORMAL)
        self.explanation_text.delete(1.0, tk.END)
        if content:
            self.explanation_text.insert(tk.END, content)
        self.explanation_text.config(state=tk.DISABLED)
