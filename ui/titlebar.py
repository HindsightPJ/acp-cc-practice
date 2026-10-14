"""Frameless 自绘标题栏（F 方案标题栏情况③，Win10/11/浅色系统观感完全一致）。

规格（docs/design/proposal_F_titlebar_win10.html 情况③）：
- 44px 站牌条 = 标题栏：brand + 模式 tag + 窗口按钮（50px 宽）；
- 窗口按钮自绘：min/max/close，close hover #e81123（Windows 惯例红）；
- startSystemMove()（Qt 6.5+）保原生拖拽手感，双击切换最大化；
- 放弃 Snap Layout（Win11 专属，Win10 无此功能，设计基线已确认）；
- 边缘 resize 经 _ResizeFilter 在窗口级鼠标事件上用 startSystemResize()
  实现（窗口需 setMouseTracking(True)，由 setup_frameless 统一设置）。

用法（main_window 接入）：
    setup_frameless(self)                       # 去 frame + 边缘 resize
    root_layout.addWidget(TitleBar(tag="PRACTICE"))  # 站牌条置顶
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

BRAND_TEXT = "ACP·云算题库"

_TITLEBAR_HEIGHT = 44
_BTN_WIDTH = 50
_EDGE = 8  # 边缘 resize 热区宽度（px）

# 边缘位（与 Qt.Edge 数值一致：Left=1 Top=2 Right=4 Bottom=8）
# PySide6 的 QFlags 不支持 int() 直转，故全程用 int 位运算，仅在调用
# startSystemResize 时转回 Qt.Edges
_LEFT, _TOP, _RIGHT, _BOTTOM = 1, 2, 4, 8

# 边缘组合 → 光标形状
_EDGE_CURSORS: tuple[tuple[int, Qt.CursorShape], ...] = (
    (_LEFT | _TOP, Qt.CursorShape.SizeFDiagCursor),
    (_RIGHT | _BOTTOM, Qt.CursorShape.SizeFDiagCursor),
    (_RIGHT | _TOP, Qt.CursorShape.SizeBDiagCursor),
    (_LEFT | _BOTTOM, Qt.CursorShape.SizeBDiagCursor),
    (_LEFT | _RIGHT, Qt.CursorShape.SizeHorCursor),
    (_TOP | _BOTTOM, Qt.CursorShape.SizeVerCursor),
)


class TitleBar(QFrame):
    """站牌条标题栏：brand + tag + 窗口按钮，空白菜区可拖拽移动窗口。"""

    def __init__(self, parent: QWidget | None = None, tag: str = "") -> None:
        super().__init__(parent)
        self.setObjectName("titlebar")
        self.setFixedHeight(_TITLEBAR_HEIGHT)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 0, 0, 0)
        layout.setSpacing(14)
        self._layout = layout

        brand = QLabel(BRAND_TEXT, self)
        brand.setObjectName("tbBrand")
        layout.addWidget(brand)

        self._tag = QLabel("", self)
        self._tag.setObjectName("tbTag")
        self._tag.setVisible(False)
        layout.addWidget(self._tag)
        self.set_tag(tag)

        layout.addStretch(1)

        self._btn_min = self._make_btn("—", "win", self._show_minimized)
        self._btn_max = self._make_btn("▢", "win", self._toggle_maximized)
        self._btn_close = self._make_btn("✕", "close", self._close_window)
        # close 按钮挂专用 role，QSS 的 [role="close"]:hover 红底规则生效
        self._btn_close.setProperty("role", "close")

    def set_tag(self, text: str) -> None:
        """设置模式 tag（如 PRACTICE / EXAM），空串隐藏。"""
        normalized = text.strip()
        self._tag.setText(normalized.upper())
        self._tag.setVisible(bool(normalized))

    # -------------------------------------------------------------- 按钮
    def _make_btn(self, symbol: str, role: str, slot: Callable[[], None]) -> QPushButton:
        btn = QPushButton(symbol, self)
        btn.setObjectName("winBtn")
        btn.setProperty("role", role)
        btn.setFixedSize(_BTN_WIDTH, _TITLEBAR_HEIGHT)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setCursor(Qt.CursorShape.ArrowCursor)
        btn.clicked.connect(slot)
        self._layout.addWidget(btn)
        return btn

    def _show_minimized(self) -> None:
        self.window().showMinimized()

    def _toggle_maximized(self) -> None:
        window = self.window()
        if window.isMaximized():
            window.showNormal()
        else:
            window.showMaximized()

    def _close_window(self) -> None:
        self.window().close()

    # -------------------------------------------------------------- 拖拽
    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt 命名
        if event.button() == Qt.MouseButton.LeftButton:
            # 系统级拖拽（原生手感，跨多显示器跟随）；按钮区已被子控件消费
            self.window().startSystemMove()  # type: ignore[attr-defined]  # PySide6 stub 缺口
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt 命名
        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_maximized()
        super().mouseDoubleClickEvent(event)


class _ResizeFilter(QObject):
    """窗口级边缘 resize 过滤器：8px 热区内 hover 换光标、按下 startSystemResize。

    依赖：窗口 setMouseTracking(True)（setup_frameless 统一设置），且热区
    落在未被交互子控件覆盖的空白处——QLabel/QFrame 默认忽略鼠标事件并向上
    传播，事件最终到达窗口被本过滤器截获。
    """

    def __init__(self, window: QWidget) -> None:
        super().__init__(window)
        self._window = window

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt 命名
        if obj is not self._window:
            return False
        etype = event.type()
        if etype == QEvent.Type.MouseMove:
            self._update_cursor(event)
        elif etype == QEvent.Type.MouseButtonPress:
            if self._try_start_resize(event):
                return True
        return False

    def _edges_at(self, event: QEvent) -> int:
        pos = event.position().toPoint()  # type: ignore[attr-defined]  # PySide6 stub 缺口
        rect = self._window.rect()
        edges = 0
        if pos.x() <= _EDGE:
            edges |= _LEFT
        if pos.x() >= rect.width() - _EDGE:
            edges |= _RIGHT
        if pos.y() <= _EDGE:
            edges |= _TOP
        if pos.y() >= rect.height() - _EDGE:
            edges |= _BOTTOM
        return edges

    def _update_cursor(self, event: QEvent) -> None:
        window = self._window
        if window.isMaximized() or window.isFullScreen():
            window.unsetCursor()
            return
        edges = self._edges_at(event)
        window.setCursor(_cursor_for_edges(edges))

    def _try_start_resize(self, event: QEvent) -> bool:
        mouse = event
        is_press = mouse.type() == QEvent.Type.MouseButtonPress
        if not is_press or mouse.button() != Qt.MouseButton.LeftButton:  # type: ignore[attr-defined]  # PySide6 stub 缺口
            return False
        window = self._window
        if window.isMaximized() or window.isFullScreen():
            return False
        edges = self._edges_at(event)
        if not edges:
            return False
        window.startSystemResize(Qt.Edges(edges))  # type: ignore[attr-defined]  # PySide6 stub 缺口
        return True


def _cursor_for_edges(edges: int) -> Qt.CursorShape:
    for mask, cursor in _EDGE_CURSORS:
        if edges & mask == mask and edges & ~mask == 0:
            return cursor
    return Qt.CursorShape.ArrowCursor


def setup_frameless(window: QWidget) -> None:
    """把窗口配置为 Frameless + 边缘 resize（须在 show() 之前调用）。"""
    window.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
    window.setMouseTracking(True)
    window.installEventFilter(_ResizeFilter(window))
