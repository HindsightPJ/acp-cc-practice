"""PracticePanel - 可复用的练习视图组件。

P2: 将 PracticeMode 与 WrongBook 错题练习中重复的练习视图抽离为统一组件，
降低视图层重复代码，同时保持两种使用场景的差异化配置能力。

P3: 题干+选项+答案/解析三段卡片复用 QuestionDetailCard，进一步消除样板代码。
操作栏通过 insert_action_bar 回调插入到选项卡和答案/解析卡之间，保持原视觉布局。
"""

import tkinter as tk
from tkinter import messagebox
from typing import Callable, cast

from .theme import theme, font_ui, font_ui_semibold, create_primary_button, create_normal_button
from .option_row import OptionRow
from .practice_session import PracticeSession
from .question_detail_card import QuestionDetailCard, get_question_type_style


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
        on_finish: Callable[[], None] | None = None,
        on_submit: Callable[[], None] | None = None,
        show_explanation: bool = True,
        show_progress_bar: bool = True,
        show_prev_button: bool = True,
        show_type_label: bool = True,
        question_height: int = 4,
    ) -> None:
        super().__init__(parent, bg=theme.BG_PAGE)
        self.session = session
        self.on_finish = on_finish
        self.on_submit = on_submit
        self.show_explanation = show_explanation
        self.show_progress_bar = show_progress_bar
        self.show_prev_button = show_prev_button
        self.show_type_label = show_type_label
        self.question_height = question_height

        self.option_cards: list[OptionRow] = []
        # P1-5: 缓存容器宽度，避免切题时调用 update_idletasks 阻塞主线程
        self._cached_width: int = 0
        self.bind("<Configure>", self._on_configure)

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
            self.type_label: tk.Label | None = tk.Label(
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
            self.progress_bar_fill: tk.Frame | None = tk.Frame(progress_bg, bg=theme.ACCENT, width=0, height=3)
            self.progress_bar_fill.place(x=0, y=0, relheight=1.0)
            self.progress_value: tk.DoubleVar | None = tk.DoubleVar(value=0)
        else:
            self.progress_bar_fill = None
            self.progress_value = None

        # 题干+选项+操作栏+答案/解析：复用 QuestionDetailCard
        # 操作栏通过 insert_action_bar 回调插入到选项卡和答案/解析卡之间，保持原视觉布局
        self.detail_card = QuestionDetailCard(
            self,
            on_option_click=self.handle_option_click,
            question_height=self.question_height,
            show_explanation=self.show_explanation,
            answer_placeholder="提交答案后查看解析",
            option_pady=4,
            insert_action_bar=self._build_action_bar,
        )
        self.detail_card.pack(fill=tk.BOTH, expand=True)

        # 别名：保留对 QuestionDetailCard 内部组件的引用，便于 load_current_question / submit_answer 操作
        # _build_ui 已保证 question_text / answer_label 在 QuestionDetailCard 中被创建，使用 cast 收窄类型
        self.question_text = cast(tk.Text, self.detail_card.question_text)
        self.option_cards = self.detail_card.option_cards
        self.result_label = cast(tk.Label, self.detail_card.answer_label)
        self.explanation_text = self.detail_card.explanation_text

    def _build_action_bar(self, container: tk.Frame) -> None:
        """构建操作栏（提交/上一题/下一题 + 统计）。

        由 QuestionDetailCard 在选项卡和答案/解析卡之间 pack，保持
        PracticePanel 原"题干 → 选项 → 操作栏 → 答案/解析"的视觉布局。
        """
        action_bar = tk.Frame(container, bg=theme.BG_PAGE)
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

        # P3: 题干 + 选项 + 清空答案/解析状态由 QuestionDetailCard 统一渲染
        self.detail_card.show_question(question)

        if self.type_label is not None:
            type_text, type_fg = get_question_type_style(question.type)
            self.type_label.configure(text=type_text, fg=type_fg)

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

        # P3: 答案标签、解析、选项高亮由 QuestionDetailCard 统一渲染
        if result["is_correct"]:
            self.detail_card.set_answer_label("回答正确", fg=theme.GREEN)
        else:
            self.detail_card.set_answer_label(
                f"回答错误，正确答案: {result['correct_answer']}", fg=theme.RED
            )

        explanation = question.explanation or "暂无解析"
        if len(explanation) < 5:
            explanation = "暂无详细解析"
        self.detail_card.set_explanation(explanation)

        self.detail_card.set_option_result(
            question.answer, "".join(self.session.selected_answers)
        )

        self.submit_btn.configure(state=tk.DISABLED, bg=theme.BTN_DISABLED, text="已提交")
        # P2-UX: 提交后将焦点移回面板，确保方向键导航立即生效
        self.focus_set()
        if self.on_submit is not None:
            self.on_submit()
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
            # P1-5: 用缓存宽度避免 update_idletasks 阻塞切题；首次未布局时 fallback
            container_width = self._cached_width
            if container_width <= 0:
                self.update_idletasks()
                container_width = self.winfo_width()
            if container_width > 0:
                bar_width = int(container_width * (progress["percentage"] / 100))
                self.progress_bar_fill.configure(width=max(bar_width, 0))

        self._update_stats()

    def _on_configure(self, event) -> None:
        """窗口 resize 时更新缓存宽度、进度条宽度、选项文本换行宽度。"""
        self._cached_width = event.width
        # resize 时立即用新宽度重绘进度条（无需等下次切题）
        if self.progress_bar_fill is not None and self.progress_value is not None:
            percentage = self.progress_value.get()
            bar_width = int(self._cached_width * (percentage / 100))
            self.progress_bar_fill.configure(width=max(bar_width, 0))

        # P2-UX: 窗口缩放时同步更新选项文本换行宽度，避免内容被截断
        new_wrap = max(200, event.width - 100)
        for card in self.option_cards:
            card.update_wraplength(new_wrap)

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

    def handle_key_press(self, event) -> str | None:
        """处理键盘事件。

        Returns:
            若已处理并应阻止进一步传播，返回 "break"；否则返回 None。
        """
        # 由使用方提供 _handle_option_key_press 或自行处理；
        # 这里仅处理方向键导航，因为选项键需要与宿主共享基类方法。
        if event.keysym == "Right":
            self.next_question()
            return "break"
        # P1-UX: show_prev_button 只控制按钮可见性，不影响键盘上一题
        if event.keysym == "Left":
            self.prev_question()
            return "break"
        return None
