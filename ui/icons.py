"""16px Canvas 线性图标库。

Tkinter 无图标体系，侧栏导航 / 结果反馈 / 主题切换等场景的图标统一
在本模块用 Canvas 基本图元绘制（线性风格，stroke 宽度随尺寸缩放）。
新增图标：在 _ICONS 注册表中添加 drawer 函数即可，调用方只认名字。

所有图标以 (cx, cy) 为中心、按 size 等比缩放绘制；color 为前景色。
"""

import logging
import math
import tkinter as tk

logger = logging.getLogger(__name__)

_ICON_BASE_SIZE = 16.0
_ICON_BASE_STROKE = 1.5


def _stroke_width(size: float) -> float:
    """线宽随图标尺寸等比缩放（16px → 1.5）。"""
    return max(1.0, _ICON_BASE_STROKE * size / _ICON_BASE_SIZE)


def _line(
    canvas: tk.Canvas,
    cx: float,
    cy: float,
    size: float,
    color: str,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
) -> None:
    k = size / _ICON_BASE_SIZE
    canvas.create_line(
        cx + x0 * k,
        cy + y0 * k,
        cx + x1 * k,
        cy + y1 * k,
        fill=color,
        width=_stroke_width(size),
        capstyle=tk.ROUND,
    )


def _polyline(
    canvas: tk.Canvas,
    cx: float,
    cy: float,
    size: float,
    color: str,
    points: list[tuple[float, float]],
) -> None:
    k = size / _ICON_BASE_SIZE
    flat: list[float] = []
    for x, y in points:
        flat.extend((cx + x * k, cy + y * k))
    canvas.create_polygon(
        flat,
        fill="",
        outline=color,
        width=_stroke_width(size),
        joinstyle=tk.ROUND,
    )


def _draw_practice(canvas: tk.Canvas, cx: float, cy: float, size: float, color: str) -> None:
    """铅笔（练习）：斜向笔杆 + 笔尖 + 橡皮端。"""
    _line(canvas, cx, cy, size, color, -5.2, 4.6, 1.8, -2.4)
    _line(canvas, cx, cy, size, color, -3.2, 2.6, 3.8, -4.4)
    _line(canvas, cx, cy, size, color, 3.8, -4.4, 5.6, -6.2)
    _line(canvas, cx, cy, size, color, -5.2, 4.6, -3.2, 2.6)


def _draw_exam(canvas: tk.Canvas, cx: float, cy: float, size: float, color: str) -> None:
    """时钟（考试）：表盘 + 时针/分针。"""
    k = size / _ICON_BASE_SIZE
    r = 6.2 * k
    canvas.create_oval(
        cx - r, cy - r, cx + r, cy + r, outline=color, width=_stroke_width(size), fill=""
    )
    _line(canvas, cx, cy, size, color, 0, 0, 0, -3.8)
    _line(canvas, cx, cy, size, color, 0, 0, 2.8, 0.8)


def _draw_review(canvas: tk.Canvas, cx: float, cy: float, size: float, color: str) -> None:
    """卡片（背题）：圆角矩形 + 两行文字线。"""
    from .rounded import draw_round_rect

    k = size / _ICON_BASE_SIZE
    draw_round_rect(
        canvas,
        cx - 6.4 * k,
        cy - 4.6 * k,
        cx + 6.4 * k,
        cy + 4.6 * k,
        radius=1.8 * k,
        outline=color,
        width=_stroke_width(size),
    )
    _line(canvas, cx, cy, size, color, -3.6, -1.2, 3.6, -1.2)
    _line(canvas, cx, cy, size, color, -3.6, 1.4, 0.8, 1.4)


def _draw_wrong(canvas: tk.Canvas, cx: float, cy: float, size: float, color: str) -> None:
    """警示（错题本）：三角 + 感叹号。"""
    _polyline(canvas, cx, cy, size, color, [(-6.2, 4.4), (0.0, -5.0), (6.2, 4.4), (-6.2, 4.4)])
    _line(canvas, cx, cy, size, color, 0, 0.6, 0, -1.8)
    k = size / _ICON_BASE_SIZE
    canvas.create_oval(
        cx - 0.9 * k, cy + 1.7 * k, cx + 0.9 * k, cy + 3.5 * k, fill=color, outline=""
    )


def _draw_star(canvas: tk.Canvas, cx: float, cy: float, size: float, color: str) -> None:
    """实心五角星（收藏）。"""
    k = size / _ICON_BASE_SIZE
    r_out, r_in = 6.8 * k, 2.8 * k
    points: list[float] = []
    for i in range(10):
        r = r_out if i % 2 == 0 else r_in
        a = math.radians(-90 + i * 36)
        points.extend((cx + r * math.cos(a), cy + r * math.sin(a)))
    canvas.create_polygon(points, fill=color, outline="")


def _draw_check(canvas: tk.Canvas, cx: float, cy: float, size: float, color: str) -> None:
    """对勾（正确）。"""
    _polyline(canvas, cx, cy, size, color, [(-5.2, 0.2), (-1.6, 3.8), (5.4, -4.2)])


def _draw_cross(canvas: tk.Canvas, cx: float, cy: float, size: float, color: str) -> None:
    """叉号（错误）。"""
    _line(canvas, cx, cy, size, color, -4.2, -4.2, 4.2, 4.2)
    _line(canvas, cx, cy, size, color, -4.2, 4.2, 4.2, -4.2)


def _draw_mark(canvas: tk.Canvas, cx: float, cy: float, size: float, color: str) -> None:
    """旗标（标记）。"""
    _line(canvas, cx, cy, size, color, 0, -5.4, 0, 5.4)
    _polyline(canvas, cx, cy, size, color, [(0.0, -5.4), (4.6, -3.8), (0.0, -2.2)])


def _draw_moon(canvas: tk.Canvas, cx: float, cy: float, size: float, color: str) -> None:
    """月牙（切换到深色主题）。"""
    k = size / _ICON_BASE_SIZE
    r_out = 6.6 * k
    r_in = 5.4 * k
    offset = 3.0 * k
    points: list[float] = []
    for i in range(13):
        a = math.radians(55 + i * 20)
        points.extend((cx + r_out * math.cos(a), cy + r_out * math.sin(a)))
    for i in range(13):
        a = math.radians(295 - i * 20)
        points.extend((cx + offset + r_in * math.cos(a), cy + r_in * math.sin(a)))
    canvas.create_polygon(points, fill=color, outline="")


def _draw_sun(canvas: tk.Canvas, cx: float, cy: float, size: float, color: str) -> None:
    """太阳（切换到浅色主题）。"""
    k = size / _ICON_BASE_SIZE
    canvas.create_oval(
        cx - 3.8 * k,
        cy - 3.8 * k,
        cx + 3.8 * k,
        cy + 3.8 * k,
        outline=color,
        width=_stroke_width(size),
        fill="",
    )
    for i in range(8):
        a = math.radians(i * 45)
        _line(
            canvas,
            cx,
            cy,
            size,
            color,
            5.2 * math.cos(a),
            5.2 * math.sin(a),
            6.9 * math.cos(a),
            6.9 * math.sin(a),
        )


_ICONS = {
    "practice": _draw_practice,
    "exam": _draw_exam,
    "review": _draw_review,
    "wrong": _draw_wrong,
    "star": _draw_star,
    "check": _draw_check,
    "cross": _draw_cross,
    "mark": _draw_mark,
    "moon": _draw_moon,
    "sun": _draw_sun,
}


def draw_icon(
    canvas: tk.Canvas, name: str, cx: float, cy: float, size: int = 16, color: str = "#000000"
) -> None:
    """在 canvas 上以 (cx, cy) 为中心绘制指定名称的图标。

    Args:
        canvas: 目标画布
        name: 图标名（见 _ICONS 注册表）
        cx: 中心 x（画布坐标）
        cy: 中心 y（画布坐标）
        size: 图标边长（px，默认 16，随尺寸等比缩放）
        color: 前景色

    未知图标名记 warning 日志后跳过（不静默）。
    """
    drawer = _ICONS.get(name)
    if drawer is None:
        logger.warning("未知图标名: %s（跳过绘制）", name)
        return
    drawer(canvas, float(cx), float(cy), float(size), color)
