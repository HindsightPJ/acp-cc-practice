"""就绪度环组件（分段渐变弧）。

页面 signature 元素：把「练习覆盖率 × 正确率」合成单一弧线，一眼可见
离考试还差多远，避免堆砌「已练 / 正确率 / 连击」四个数字。

2026-10-14 重设计：升级为侧栏 Hero（104px / 8px 线宽），进度弧改 12 段
颜色插值（Tk create_arc 无渐变也无 linecap，分段 + 接缝圆点是对冲方案，
见 TASK_PLAN K5）；中心大数字 + 「就绪度」副标。
"""

import math
import tkinter as tk

from .constants import RING_SIZE, RING_THICKNESS
from .theme import font_display, font_ui, theme

# 渐变弧分段数（12 段 × 30°），段间重叠 1° 遮缝 + 接缝圆点模拟圆头
RING_SEGMENTS = 12
RING_OVERLAP_DEG = 1.0


def _parse_hex(hex_color: str) -> tuple[int, int, int]:
    """解析 #rrggbb → (r, g, b)。"""
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _lerp_color(c1: str, c2: str, t: float) -> str:
    """两 hex 色线性插值（t: 0 → c1，1 → c2）。"""
    r1, g1, b1 = _parse_hex(c1)
    r2, g2, b2 = _parse_hex(c2)
    r = round(r1 + (r2 - r1) * t)
    g = round(g1 + (g2 - g1) * t)
    b = round(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


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

    # ------------------------------------------------------------------ 绘制
    def _draw(self) -> None:
        self.delete("all")
        size = self._size
        thickness = self._thickness
        # create_arc 的描边沿路径居中绘制；预留完整 thickness 边距，
        # 保证任何 thickness 下弧线外缘都不贴边裁切
        pad = thickness
        bbox = (pad, pad, size - pad, size - pad)
        cx = size / 2
        cy = size / 2
        radius = (size - 2 * pad) / 2
        cap_r = thickness / 2

        # 背景轨道环（整圆）
        self.create_arc(
            bbox, outline=theme.RING_TRACK, width=thickness, style="arc", start=90, extent=360
        )

        # 进度弧：12 段颜色插值，从 12 点钟方向顺时针
        extent = -360 * self._mastery  # Tkinter arc extent 负值=顺时针
        if self._mastery > 0:
            seg_extent = abs(extent) / RING_SEGMENTS
            for i in range(RING_SEGMENTS):
                color = _lerp_color(theme.RING_START, theme.RING_END, i / (RING_SEGMENTS - 1))
                start = 90 - seg_extent * i
                # 段间重叠 1° 遮缝（create_arc 无 linecap， butt 端）
                self.create_arc(
                    bbox,
                    outline=color,
                    width=thickness,
                    style="arc",
                    start=start,
                    extent=-(seg_extent + RING_OVERLAP_DEG),
                )
                # 接缝圆点：直径 = 线宽，模拟圆头端帽的珠链质感
                theta = math.radians(start)
                jx = cx + radius * math.cos(theta)
                jy = cy - radius * math.sin(theta)
                self.create_oval(
                    jx - cap_r, jy - cap_r, jx + cap_r, jy + cap_r, fill=color, outline=""
                )
            # 末端圆帽
            end_theta = math.radians(90 + extent)
            ex = cx + radius * math.cos(end_theta)
            ey = cy - radius * math.sin(end_theta)
            end_color = _lerp_color(theme.RING_START, theme.RING_END, 1.0)
            self.create_oval(
                ex - cap_r, ey - cap_r, ex + cap_r, ey + cap_r, fill=end_color, outline=""
            )

        # 中心百分比与标签：以环心为基准 anchor 定位，随字号/尺寸自适应
        pct = int(round(self._mastery * 100))
        self.create_text(
            cx,
            cy - 4,
            text=f"{pct}%",
            fill=theme.INK_TEXT,
            font=font_display(19, True),
            anchor="s",
        )
        self.create_text(
            cx, cy + 8, text="就绪度", fill=theme.INK_TEXT_MUTED, font=font_ui(10), anchor="n"
        )
