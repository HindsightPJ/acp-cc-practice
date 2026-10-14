"""就绪度环组件。"""

import math
import tkinter as tk

from .theme import theme, font_display, font_ui


RING_SIZE = 88
RING_THICKNESS = 6


class MasteryRing(tk.Canvas):
    """就绪度环：把「练习覆盖率 × 正确率」合成为单一指标。

    这是页面的 signature 元素——把用户真正关心的「我离考试还差多远」
    做成一眼可见的弧线，避免堆砌「已练 / 正确率 / 连击」四个数字。
    """

    def __init__(
        self, parent: tk.Misc, size: int = RING_SIZE, thickness: int = RING_THICKNESS
    ) -> None:
        super().__init__(parent, width=size, height=size, bg=theme.INK, highlightthickness=0, bd=0)
        self._size = size
        self._thickness = thickness
        self._mastery = 0.0  # 0.0 ~ 1.0
        self._draw()

    def set_mastery(self, mastery: float) -> None:
        """mastery: 0.0 ~ 1.0。负值或 NaN 视作 0；值不变时不重绘。"""
        try:
            m = float(mastery)
        except (TypeError, ValueError):
            m = 0.0
        if math.isnan(m) or math.isinf(m):
            m = 0.0
        m = max(0.0, min(1.0, m))
        if m == self._mastery:
            return
        self._mastery = m
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        size = self._size
        thickness = self._thickness
        # create_arc 的描边沿路径居中绘制；预留完整 thickness 边距，
        # 保证任何 thickness 下弧线外缘都不贴边裁切
        pad = thickness
        bbox = (pad, pad, size - pad, size - pad)
        cx = size / 2

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
            self._draw_round_caps(bbox, extent)

        # 中心百分比与标签：以环心为基准 anchor 定位，随字号/尺寸自适应，
        # 不再依赖与字号强耦合的硬编码偏移
        pct = int(round(self._mastery * 100))
        self.create_text(
            cx,
            cx - 2,
            text=f"{pct}%",
            fill=theme.INK_TEXT,
            font=font_display(18, True),
            anchor="s",
        )
        self.create_text(
            cx, cx + 2, text="就绪度", fill=theme.INK_TEXT_MUTED, font=font_ui(9), anchor="n"
        )

    def _draw_round_caps(self, bbox: tuple[int, int, int, int], extent: float) -> None:
        """在进度弧两端画直径等于线宽的圆点，模拟圆头端帽（纸感柔和风）。"""
        r = (bbox[2] - bbox[0]) / 2
        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2
        cap_radius = self._thickness / 2
        # Tk 角度以 3 点钟方向为 0°、屏幕坐标逆时针（y 向下故公式中 sin 取负）
        start_theta = math.radians(90)
        end_theta = math.radians(90 + extent)
        for theta in (start_theta, end_theta):
            x = cx + r * math.cos(theta)
            y = cy - r * math.sin(theta)
            self.create_oval(
                x - cap_radius,
                y - cap_radius,
                x + cap_radius,
                y + cap_radius,
                fill=theme.ACCENT,
                outline="",
            )
