"""统一的选项行组件。

四种模式（练习 / 考试 / 背题 / 错题）共用同一个 OptionRow，避免四套样式
逻辑漂移。状态机：idle → hover → selected；提交后进入结果态：
correct / wrong / revealed（正确答案高亮但用户未选）。

调用方负责：
1. 实例化时传 letter / text / on_click；
2. 切题前 reset() 清状态；
3. 用户点击触发 on_click(letter) 后，调用方决定 set_selected(True/False)；
4. 提交答案后调用 set_result(is_correct, is_selected_answer)。
"""

import tkinter as tk
from typing import Optional, Callable

from .theme import Theme, font_ui, font_ui_semibold

theme = Theme()


class OptionRow(tk.Frame):
    """单行选项，左侧字母圆角块 + 右侧文字。"""

    def __init__(
        self,
        parent,
        letter: str,
        text: str = "",
        on_click: Optional[Callable[[str], None]] = None,
        wraplength: int = 700,
        **kwargs,
    ):
        super().__init__(parent, bg=theme.BG_CARD, **kwargs)

        self.letter = letter
        self.option_text = text
        self.on_click = on_click
        self.wraplength = wraplength

        # 状态
        self.is_selected = False
        self.is_correct: Optional[bool] = None  # None=未判分；True/False=已判分
        self.is_answered_selected = False  # 提交后用户是否选了此项

        self.configure(
            cursor="hand2",
            highlightbackground=theme.BORDER,
            highlightthickness=1,
            highlightcolor=theme.BORDER,
        )

        self._build_ui()
        self._bind_events()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        # Glassmorphism 风：更大留白 + Canvas 绘制真圆字母块（非方块）
        inner = tk.Frame(self, bg=theme.BG_CARD)
        inner.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)
        self._inner = inner

        # Canvas 绘制真圆：create_oval 在 28×28 画布上画直径 24 的圆，
        # 留 2px 边距让圆"浮"在行背景上，避免贴边显局促。
        self._letter_circle = tk.Canvas(
            inner, width=28, height=28, bg=theme.BG_CARD, highlightthickness=0, bd=0
        )
        self._letter_circle.pack(side=tk.LEFT, padx=(0, 14))
        self._circle_oval = self._letter_circle.create_oval(
            2, 2, 26, 26, fill=theme.BG_INPUT, outline=""
        )
        self._circle_text = self._letter_circle.create_text(
            14, 14, text=self.letter, font=font_ui_semibold(11), fill=theme.TEXT_MUTED
        )

        self._text_label = tk.Label(
            inner,
            text=self.option_text,
            font=font_ui(11),
            fg=theme.TEXT_PRIMARY,
            bg=theme.BG_CARD,
            wraplength=self.wraplength,
            justify=tk.LEFT,
            anchor=tk.W,
        )
        self._text_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _bind_events(self) -> None:
        # Canvas 上的 item 事件默认冒泡到 Canvas，bind Canvas 即可触发
        widgets = [self, self._inner, self._letter_circle, self._text_label]
        for w in widgets:
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)
            w.bind("<Button-1>", self._on_click)

    # -------------------------------------------------------------- 事件
    def _on_enter(self, event=None) -> None:
        if not self.is_selected and self.is_correct is None:
            self._apply_hover_style()

    def _on_leave(self, event=None) -> None:
        if not self.is_selected and self.is_correct is None:
            self._apply_idle_style()

    def _on_click(self, event=None) -> None:
        if self.on_click:
            self.on_click(self.letter)

    # -------------------------------------------------------------- 状态
    def update_text(self, text: str) -> None:
        self.option_text = text
        self._text_label.configure(text=text)

    def update_wraplength(self, wraplength: int) -> None:
        self.wraplength = max(wraplength, 50)
        self._text_label.configure(wraplength=self.wraplength)

    def reset(self) -> None:
        """切题时清空所有状态。"""
        self.is_selected = False
        self.is_correct = None
        self.is_answered_selected = False
        self._apply_idle_style()

    def set_selected(self, selected: bool) -> None:
        """用户切换选中态（未提交前）。"""
        self.is_selected = selected
        if selected:
            self._apply_selected_style()
        else:
            self._apply_idle_style()

    def set_result(self, is_correct: bool, is_selected_answer: bool) -> None:
        """提交后标记结果态。

        - is_correct=True, is_selected_answer=True  → 用户选对
        - is_correct=True, is_selected_answer=False → 正确答案但用户没选
        - is_correct=False, is_selected_answer=True → 用户选错
        - is_correct=False, is_selected_answer=False→ 不显示（调用方应过滤）
        """
        self.is_correct = is_correct
        self.is_answered_selected = is_selected_answer
        self.is_selected = False  # 结果态不再用选中态样式

        if is_correct and is_selected_answer:
            self._apply_style(
                circle_bg=theme.GREEN,
                circle_fg=theme.CORRECT_TEXT,
                row_bg=theme.GREEN_BG,
                text_fg=theme.GREEN_TEXT,
                icon="✓",
            )
        elif is_correct and not is_selected_answer:
            self._apply_style(
                circle_bg=theme.GREEN_BG,
                circle_fg=theme.GREEN_TEXT,
                row_bg=theme.GREEN_BG,
                text_fg=theme.GREEN_TEXT,
                icon=self.letter,
            )
        elif not is_correct and is_selected_answer:
            self._apply_style(
                circle_bg=theme.RED,
                circle_fg=theme.WRONG_TEXT,
                row_bg=theme.RED_BG,
                text_fg=theme.RED_TEXT,
                icon="✗",
            )
        # 第四种情况：不显示，调用方应不调用本方法

    def reveal_correct(self) -> None:
        """背题模式：高亮正确答案。"""
        self.is_correct = True
        self.is_answered_selected = False
        self._apply_style(
            circle_bg=theme.GREEN_BG,
            circle_fg=theme.GREEN_TEXT,
            row_bg=theme.GREEN_BG,
            text_fg=theme.GREEN_TEXT,
            icon=self.letter,
        )

    # -------------------------------------------------------------- 样式
    def _apply_idle_style(self) -> None:
        # macOS 风：白底 + 极淡灰边框，字母圆块灰底淡字
        self._apply_style(
            circle_bg=theme.BG_INPUT,
            circle_fg=theme.TEXT_MUTED,
            row_bg=theme.BG_CARD,
            text_fg=theme.TEXT_PRIMARY,
            icon=self.letter,
            border_color=theme.BORDER,
            border_thickness=1,
        )

    def _apply_hover_style(self) -> None:
        # 克制 hover：浅灰底（非蓝），仅字母圆块转浅蓝提示可点击
        self._apply_style(
            circle_bg=theme.ACCENT_LIGHT,
            circle_fg=theme.ACCENT,
            row_bg=theme.BG_HOVER,
            text_fg=theme.TEXT_PRIMARY,
            icon=self.letter,
            border_color=theme.BORDER,
            border_thickness=1,
        )

    def _apply_selected_style(self) -> None:
        # 选中态：浅蓝底 + 蓝色边框 1.5px + 蓝色字母圆块白字 + 文字深蓝
        self._apply_style(
            circle_bg=theme.ACCENT,
            circle_fg=theme.SELECTED_TEXT,
            row_bg=theme.ACCENT_LIGHT,
            text_fg=theme.ACCENT_HOVER,
            icon=self.letter,
            border_color=theme.ACCENT,
            border_thickness=2,
        )

    def _apply_style(
        self,
        *,
        circle_bg: str,
        circle_fg: str,
        row_bg: str,
        text_fg: str,
        icon: str,
        border_color: Optional[str] = None,
        border_thickness: Optional[int] = None,
    ) -> None:
        if border_color is not None:
            self.configure(
                highlightbackground=border_color,
                highlightcolor=border_color,
                highlightthickness=border_thickness if border_thickness is not None else 1,
            )
        self._inner.configure(bg=row_bg)
        # Canvas 背景跟行背景（让圆"浮"在行上），圆形 fill 用 circle_bg
        self._letter_circle.configure(bg=row_bg)
        self._letter_circle.itemconfig(self._circle_oval, fill=circle_bg)
        self._letter_circle.itemconfig(self._circle_text, fill=circle_fg, text=icon)
        self._text_label.configure(bg=row_bg, fg=text_fg)
