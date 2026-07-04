"""app_state.py 单元测试。

聚焦 save_safe 的新行为（P0-4: 不再静默吞错）：
  - 成功时返回 True
  - 失败时返回 False，不抛异常，记录 warning 日志
"""
from unittest.mock import MagicMock

import pytest

from app_state import AppState
from data_manager import DataSaveError


@pytest.fixture
def app_state():
    """构建带 mock data_manager 的 AppState。"""
    data_manager = MagicMock()
    return AppState(data_manager, progress={})


def test_save_safe_success_returns_true(app_state):
    """save 成功时 save_safe 返回 True。"""
    app_state._data_manager.save_progress = MagicMock()
    assert app_state.save_safe() is True
    app_state._data_manager.save_progress.assert_called_once()


def test_save_safe_oserror_returns_false(app_state):
    """save 抛 OSError 时 save_safe 返回 False，不抛异常。"""
    app_state._data_manager.save_progress = MagicMock(side_effect=OSError("disk full"))
    assert app_state.save_safe() is False


def test_save_safe_datasaveerror_returns_false(app_state):
    """save 抛 DataSaveError 时 save_safe 返回 False，不抛异常。"""
    app_state._data_manager.save_progress = MagicMock(side_effect=DataSaveError("write failed"))
    assert app_state.save_safe() is False


def test_save_safe_valueerror_returns_false(app_state):
    """save 抛 ValueError 时 save_safe 返回 False，不抛异常。"""
    app_state._data_manager.save_progress = MagicMock(side_effect=ValueError("bad data"))
    assert app_state.save_safe() is False


def test_save_safe_logs_warning_on_failure(app_state, caplog):
    """save 失败时记录 warning 日志（P0-4: 不再静默吞错）。"""
    app_state._data_manager.save_progress = MagicMock(side_effect=OSError("disk full"))
    with caplog.at_level("WARNING", logger="app_state"):
        app_state.save_safe()
    assert any("保存学习进度失败" in record.message for record in caplog.records)
