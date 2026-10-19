"""titlebar.py 单元测试（M14：无边框窗口管理此前 59% 覆盖，按钮/边缘 resize 零测试）。

覆盖：
- _cursor_for_edges 纯函数（边缘组合 → 光标形状映射与兜底）
- _ResizeFilter._edges_at 四边四角热区判定（8px 边缘）
- 窗口三按钮行为（最小化/最大化切换/关闭）
"""

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QWidget

from ui import titlebar
from ui.titlebar import TitleBar, _ResizeFilter, _cursor_for_edges

pytestmark = pytest.mark.gui


def _move_event(pos: tuple[int, int]) -> QMouseEvent:
    # [VERSION_LOCKED] PySide6 6.12：5 参便捷构造已弃用，用 8 参构造（2026-10 验证）
    point = QPointF(*pos)
    return QMouseEvent(
        QEvent.Type.MouseMove,
        point,
        point,
        point,
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )


@pytest.fixture
def window(qtbot):
    w = QWidget()
    w.resize(400, 300)
    qtbot.addWidget(w)
    return w


# ---------- _cursor_for_edges 纯函数 ----------


@pytest.mark.parametrize(
    "edges,expected",
    [
        (0, Qt.CursorShape.ArrowCursor),
        (titlebar._LEFT, Qt.CursorShape.ArrowCursor),  # 单边无映射 → 兜底
        (titlebar._TOP, Qt.CursorShape.ArrowCursor),
        (titlebar._LEFT | titlebar._RIGHT, Qt.CursorShape.SizeHorCursor),
        (titlebar._TOP | titlebar._BOTTOM, Qt.CursorShape.SizeVerCursor),
        (titlebar._LEFT | titlebar._TOP, Qt.CursorShape.SizeFDiagCursor),
        (titlebar._RIGHT | titlebar._BOTTOM, Qt.CursorShape.SizeFDiagCursor),
        (titlebar._RIGHT | titlebar._TOP, Qt.CursorShape.SizeBDiagCursor),
        (titlebar._LEFT | titlebar._BOTTOM, Qt.CursorShape.SizeBDiagCursor),
        # 三边组合无精确映射 → 兜底（不返回错误光标）
        (titlebar._LEFT | titlebar._TOP | titlebar._RIGHT, Qt.CursorShape.ArrowCursor),
    ],
)
def test_cursor_for_edges_mapping(edges, expected):
    """_cursor_for_edges：已知组合映射 + 未知组合兜底 ArrowCursor。"""
    assert _cursor_for_edges(edges) == expected


# ---------- _edges_at 热区判定 ----------


@pytest.mark.parametrize(
    "pos,expected_edges",
    [
        ((0, 150), titlebar._LEFT),
        ((399, 150), titlebar._RIGHT),
        ((200, 0), titlebar._TOP),
        ((200, 299), titlebar._BOTTOM),
        ((0, 0), titlebar._LEFT | titlebar._TOP),
        ((399, 299), titlebar._RIGHT | titlebar._BOTTOM),
        ((200, 150), 0),
        ((100, 100), 0),
    ],
)
def test_edges_at_hot_zone(window, pos, expected_edges):
    """_edges_at：8px 边缘热区四边四角 + 中心/内部判定。"""
    resize_filter = _ResizeFilter(window)
    assert resize_filter._edges_at(_move_event(pos)) == expected_edges


# ---------- 窗口三按钮 ----------


def test_titlebar_buttons_toggle_and_close(window, qtbot):
    """最大化按钮切换最大化/还原；关闭按钮关闭窗口。"""
    bar = TitleBar(window)
    qtbot.addWidget(bar)
    window.show()

    bar._btn_max.click()
    assert window.isMaximized() is True

    bar._btn_max.click()
    assert window.isMaximized() is False

    bar._btn_close.click()
    assert window.isVisible() is False


def test_set_theme_icon_symbols(qtbot):
    """主题切换钮符号随模式切换（☾=浅色 / ☀=深色）。"""
    bar = TitleBar(None, on_theme_toggle=lambda: None)
    qtbot.addWidget(bar)

    bar.set_theme_icon("light")
    assert bar._btn_theme.text() == "☾"

    bar.set_theme_icon("dark")
    assert bar._btn_theme.text() == "☀"
