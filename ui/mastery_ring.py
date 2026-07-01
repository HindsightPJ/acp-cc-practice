"""就绪度环组件。"""

import math
import tkinter as tk

from .theme import Theme, font_display, font_ui

theme = Theme()


RING_SIZE = 88
RING_THICKNESS = 6


class MasteryRing(tk.Canvas):
    """就绪度环：把「练习覆盖率 × 正确率」合成为单一指标。

    这是页面的 signature 元素——把用户真正关心的「我离考试还差多远」
    做成一眼可见的弧线，避免堆砌「已练 / 正确率 / 连击」四个数字。
    """

    def __init__(self, parent, size: int = RING_SIZE, thickness: int = RING_THICKNESS) -> None:
        super().__init__(parent, width=size, height=size, bg=theme.INK, highlightthickness=0, bd=0)
        self._size = size
        self._thickness = thickness
        self._mastery = 0.0  # 0.0 ~ 1.0
        self._draw()

    def set_mastery(self, mastery: float) -> None:
        """mastery: 0.0 ~ 1.0。负值或 NaN 视作 0。"""
        try:
            m = float(mastery)
        except (TypeError, ValueError):
            m = 0.0
        if math.isnan(m) or math.isinf(m):
            m = 0.0
        self._mastery = max(0.0, min(1.0, m))
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        size = self._size
        thickness = self._thickness
        pad = thickness  # 留出描边空间
        bbox = (pad, pad, size - pad, size - pad)

        # 背景环
        self.create_arc(
            bbox, outline=theme.INK_DIVIDER, width=thickness, style="arc", start=90, extent=360
        )

        # 进度弧（从 12 点钟方向顺时针）
        extent = -360 * self._mastery  # Tkinter arc extent 负值=顺时针
        if self._mastery > 0:
            self.create_arc(
                bbox, outline=theme.ACCENT, width=thickness, style="arc", start=90, extent=extent
            )

        # 中心百分比
        pct = int(round(self._mastery * 100))
        self.create_text(
            size // 2,
            size // 2 - 6,
            text=f"{pct}%",
            fill=theme.INK_TEXT,
            font=font_display(18, True),
        )
        self.create_text(
            size // 2, size // 2 + 14, text="就绪度", fill=theme.INK_TEXT_MUTED, font=font_ui(9)
        )
