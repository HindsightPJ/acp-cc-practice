"""统一的选项行组件（圆角卡片形态）。

四种模式（练习 / 考试 / 背题 / 错题）共用同一个 OptionRow，避免四套样式
逻辑漂移。状态机：idle → hover → selected；提交后进入结果态：
correct / wrong / revealed（正确答案高亮但用户未选）。

2026-10-14 重设计：tk.Frame → RoundedCard（Canvas 圆角底），字母圆
20px，结果态右侧绘制 check/cross 线性图标；全部颜色走 theme Token。

调用方负责：
1. 实例化时传 letter / text / on_click；
2. 切题前 reset() 清状态；
3. 用户点击触发 on_click(letter) 后，调用方决定 set_selected(True/False)；
4. 提交答案后调用 set_result(is_correct, is_selected_answer)。
"""

import tkinter as tk
from typing import Any, Callable

from .constants import RADIUS_OPTION
from .icons import draw_icon
from .rounded import RoundedCard
from .theme import theme, font_ui, font_ui_semibold

# 字母圆与结果图标的尺寸（px）
CIRCLE_SIZE = 22
ICON_SIZE = 18


class OptionRow(RoundedCard):
    """单行选项：左侧字母圆 + 中间文字 + 右侧结果图标，整行圆角卡片。"""

    def __init__(
        self,
        parent: tk.Widget,
        letter: str,
        text: str = "",
        on_click: Callable[[str], None] | None = None,
        wraplength: int = 700,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            parent,
            radius=RADIUS_OPTION,
            bg=theme.BG_CARD,
            surface=theme.BG_CARD,
            border=theme.BORDER,
            border_width=1,
            padx=14,
            pady=9,
            **kwargs,
        )
        self.configure(cursor="hand2")

        self.letter = letter
        self.option_text = text
        self.on_click = on_click
        self.wraplength = wraplength

        # 状态
        self.is_selected = False
        self.is_correct: bool | None = None  # None=未判分；True/False=已判分
        self.is_answered_selected = False  # 提交后用户是否选了此项

        self._build_ui()
        self._bind_events()
        self._apply_idle_style()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        row_bg = theme.BG_CARD

        # 字母圆（Canvas 真圆）
        self._letter_circle = tk.Canvas(
            self.inner, width=CIRCLE_SIZE, height=CIRCLE_SIZE, bg=row_bg, highlightthickness=0, bd=0
        )
        self._circle_oval = self._letter_circle.create_oval(
            1, 1, CIRCLE_SIZE - 1, CIRCLE_SIZE - 1, fill=theme.BG_INPUT, outline=""
        )
        self._circle_text = self._letter_circle.create_text(
            CIRCLE_SIZE / 2,
            CIRCLE_SIZE / 2,
            text=self.letter,
            font=font_ui_semibold(11),
            fill=theme.TEXT_MUTED,
        )
        self._letter_circle.pack(side=tk.LEFT, padx=(0, 12))

        self._text_label = tk.Label(
            self.inner,
            text=self.option_text,
            font=font_ui(12),
            fg=theme.TEXT_PRIMARY,
            bg=row_bg,
            wraplength=self.wraplength,
            justify=tk.LEFT,
            anchor=tk.W,
        )
        self._text_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 右侧结果图标位（默认空）
        self._icon_canvas = tk.Canvas(
            self.inner, width=ICON_SIZE, height=ICON_SIZE, bg=row_bg, highlightthickness=0, bd=0
        )
        self._icon_canvas.pack(side=tk.RIGHT, padx=(12, 0))
        self._icon_name: str | None = None

    def _bind_events(self) -> None:
        # 整行可点：卡片本体 + 全部子控件
        widgets = [self, self.inner, self._letter_circle, self._text_label, self._icon_canvas]
        for w in widgets:
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)
            w.bind("<Button-1>", self._on_click)
            # typeshed 的 Misc.configure 无 cursor 关键字，走 item 赋值
            w["cursor"] = "hand2"

    # -------------------------------------------------------------- 事件
    def _on_enter(self, event: tk.Event | None = None) -> None:
        if not self.is_selected and self.is_correct is None:
            self._apply_hover_style()

    def _on_leave(self, event: tk.Event | None = None) -> None:
        if not self.is_selected and self.is_correct is None:
            self._apply_idle_style()

    def _on_click(self, event: tk.Event | None = None) -> None:
        if self.on_click:
            self.on_click(self.letter)

    # -------------------------------------------------------------- 状态
    def update_text(self, text: str) -> None:
        self.option_text = text
        self._text_label.configure(text=text)
        self.refit()

    def update_wraplength(self, wraplength: int) -> None:
        self.wraplength = max(wraplength, 50)
        self._text_label.configure(wraplength=self.wraplength)
        self.refit()

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
                icon="check",
                icon_color=theme.GREEN,
                border_color=theme.GREEN_BORDER,
                border_thickness=1,
            )
        elif is_correct and not is_selected_answer:
            self._apply_style(
                circle_bg=theme.GREEN_BG,
                circle_fg=theme.GREEN_TEXT,
                row_bg=theme.GREEN_BG,
                text_fg=theme.GREEN_TEXT,
                icon=self.letter,
                border_color=theme.GREEN_BORDER,
                border_thickness=1,
            )
        elif not is_correct and is_selected_answer:
            self._apply_style(
                circle_bg=theme.RED,
                circle_fg=theme.WRONG_TEXT,
                row_bg=theme.RED_BG,
                text_fg=theme.RED_TEXT,
                icon="cross",
                icon_color=theme.RED,
                border_color=theme.RED_BORDER,
                border_thickness=1,
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
            border_color=theme.GREEN_BORDER,
            border_thickness=1,
        )

    # -------------------------------------------------------------- 样式
    def _apply_idle_style(self) -> None:
        # 白底 + 极淡边框，字母圆灰底淡字
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
        # 克制 hover：浅灰底 + 字母圆转浅蓝提示可点击
        self._apply_style(
            circle_bg=theme.ACCENT_LIGHT,
            circle_fg=theme.ACCENT,
            row_bg=theme.BG_HOVER,
            text_fg=theme.TEXT_PRIMARY,
            icon=self.letter,
            border_color=theme.ACCENT_BORDER,
            border_thickness=1,
        )

    def _apply_selected_style(self) -> None:
        # 选中态：浅蓝底 + 蓝色边框 1.5px + 蓝色字母圆白字 + 右侧对勾
        self._apply_style(
            circle_bg=theme.ACCENT,
            circle_fg=theme.SELECTED_TEXT,
            row_bg=theme.BG_SELECT,
            text_fg=theme.ACCENT_HOVER,
            icon="check",
            icon_color=theme.ACCENT,
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
        border_color: str | None = None,
        border_thickness: int | None = None,
        icon_color: str | None = None,
    ) -> None:
        self.set_style(
            bg=row_bg,
            border=border_color if border_color is not None else theme.BORDER,
            border_width=float(border_thickness if border_thickness is not None else 1),
        )
        # 子控件底色跟随行背景（Tk 无级联换色）
        self._letter_circle.configure(bg=row_bg)
        self._icon_canvas.configure(bg=row_bg)
        self._letter_circle.itemconfig(self._circle_oval, fill=circle_bg)
        # 字母圆恒显字母；check/cross 只画在右侧图标位（否则会把
        # "cross"/"check" 当文字塞进 22px 圆里，2026-10-14 实测乱码）
        self._letter_circle.itemconfig(self._circle_text, fill=circle_fg, text=self.letter)
        self._text_label.configure(bg=row_bg, fg=text_fg)
        # 右侧图标：仅 selected/correct/wrong 有，其余清空
        if self._icon_name != icon:
            self._icon_canvas.delete("all")
            self._icon_name = None
        if icon in ("check", "cross"):
            draw_icon(
                self._icon_canvas,
                icon,
                ICON_SIZE / 2,
                ICON_SIZE / 2,
                14,
                icon_color if icon_color is not None else theme.ACCENT,
            )
            self._icon_name = icon
