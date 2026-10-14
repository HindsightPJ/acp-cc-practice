"""base_mode.py 单元测试（PySide6 版）。

覆盖 BaseModePage 防抖保存三件套（单发 QTimer 语义，替代 tkinter after job），
避免 tkinter 版 P2-16 类 bug（保存失败时 _pending_save 被提前清空）回归。
"""

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QMessageBox

from ui.base_mode import BaseModePage

pytestmark = pytest.mark.gui


class _TestMode(BaseModePage):
    """测试用最小子类（基类无抽象方法，直接可用）。"""

    _save_failure_message = "测试保存失败。"


class _MockAppState:
    """轻量 AppState 替代（BaseModePage 只调用 save_safe）。"""

    def __init__(self):
        self.save_safe = MagicMock(return_value=True)


@pytest.fixture
def mode(qtbot):
    widget = _TestMode(_MockAppState())
    qtbot.addWidget(widget)
    return widget


# ---------- _save_progress_delayed ----------


def test_save_progress_delayed_sets_pending_and_starts_timer(mode):
    """调用 _save_progress_delayed 后 _pending_save=True 且计时器启动。"""
    assert not mode._pending_save
    assert not mode._save_timer.isActive()

    mode._save_progress_delayed()

    assert mode._pending_save is True
    assert mode._save_timer.isActive()


def test_save_progress_delayed_restarts_timer(mode, monkeypatch, qtbot):
    """单发 QTimer start() 自带 restart 语义：等待后再次调用重置计时。"""
    monkeypatch.setattr("ui.base_mode.SAVE_DEBOUNCE_MS", 200)
    mode._save_progress_delayed()
    qtbot.wait(120)  # 防抖窗口消耗过半

    mode._save_progress_delayed()

    # 若未重置，剩余应 <100ms；重置后应接近 200ms
    remaining = mode._save_timer.remainingTime()
    assert remaining > 150


def test_debounce_timer_fires_save_on_expiry(mode, monkeypatch, qtbot):
    """防抖到期自动执行保存（QTimer 驱动，无需手动 flush）。"""
    monkeypatch.setattr("ui.base_mode.SAVE_DEBOUNCE_MS", 30)
    mode._save_progress_delayed()

    qtbot.waitUntil(lambda: mode.app_state.save_safe.call_count == 1, timeout=2000)

    assert mode._pending_save is False


# ---------- _do_save_progress ----------


def test_do_save_progress_resets_pending_on_success(mode):
    """_do_save_progress 成功时 _pending_save 重置为 False。"""
    mode._pending_save = True
    mode._do_save_progress()

    assert mode._pending_save is False
    mode.app_state.save_safe.assert_called_once()


def test_do_save_progress_keeps_pending_on_failure(mode, monkeypatch):
    """P2-16: 保存失败时 _pending_save 应保持 True，以便下次 flush 重试。"""
    mode.app_state.save_safe.return_value = False
    warned = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warned.append(a))

    mode._pending_save = True
    mode._do_save_progress()

    assert mode._pending_save is True
    mode.app_state.save_safe.assert_called_once()
    assert len(warned) == 1
    assert "测试保存失败" in warned[0][2]  # 第三个位置参数 = 消息文案


# ---------- flush_pending_save ----------


def test_flush_pending_save_saves_immediately(mode, monkeypatch):
    """flush_pending_save 停表并立即落盘（切页/关窗路径）。"""
    monkeypatch.setattr("ui.base_mode.SAVE_DEBOUNCE_MS", 60_000)
    mode._save_progress_delayed()

    mode.flush_pending_save()

    assert mode._pending_save is False
    assert not mode._save_timer.isActive()
    mode.app_state.save_safe.assert_called_once()


def test_flush_pending_save_keeps_pending_on_failure(mode, monkeypatch):
    """保存失败时 flush_pending_save 保留待存标记并提示。"""
    mode.app_state.save_safe.return_value = False
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    mode._pending_save = True

    mode.flush_pending_save()

    assert mode._pending_save is True


def test_flush_pending_save_no_op_when_not_pending(mode):
    """没有待保存时 flush_pending_save 不调用 save_safe。"""
    mode.flush_pending_save()

    assert mode._pending_save is False
    mode.app_state.save_safe.assert_not_called()


# ---------- 主窗口鸭子协议 ----------


def test_nav_count_and_modeline_default_none(mode):
    """基类默认不提供计数/modeline（None = 主窗口显示缺省值）。"""
    assert mode.nav_count() is None
    assert mode.modeline_text() is None


def test_state_changed_signal_exists(qtbot):
    """state_changed 信号可发射可接收（主窗口刷新链路的基础）。"""
    mode = _TestMode(_MockAppState())
    qtbot.addWidget(mode)
    received = []
    mode.state_changed.connect(lambda: received.append(1))

    mode.state_changed.emit()

    assert received == [1]
