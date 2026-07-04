"""base_mode.py 单元测试（P2-20）。

覆盖 BaseMode 提取到基类的防抖保存三件套行为，
避免 P2-16 类 bug（保存失败时 _pending_save 被提前清空）回归。
"""
import tkinter as tk
from unittest.mock import MagicMock

import pytest

from ui.base_mode import BaseMode


@pytest.fixture(scope='module')
def root():
    """模块级共享 Tk 实例。"""
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


class _TestMode(BaseMode):
    """测试用最小子类，满足抽象基类要求。"""

    _save_failure_message = "测试保存失败。"

    def _setup_mode_ui(self) -> None:
        pass

    def _on_key_press(self, event) -> None:
        pass


class _MockAppState:
    """可 patch 为 ui.base_mode.AppState 的轻量类，避免 isinstance 失败。"""
    def __init__(self, data_manager, progress):
        self.data_manager = data_manager
        self.progress = progress
        self.save_safe = MagicMock(return_value=True)


@pytest.fixture
def mode(root, monkeypatch):
    """提供一个已初始化的 _TestMode 实例。"""
    monkeypatch.setattr('ui.base_mode.AppState', _MockAppState)
    mode = _TestMode(root, [], MagicMock(), {})
    mode.pack()
    return mode


def test_save_progress_delayed_sets_pending_flag_and_schedules_job(mode):
    """调用 _save_progress_delayed 后 _pending_save=True 且 _after_jobs 非空。"""
    assert not mode._pending_save
    assert mode._after_jobs == []

    mode._save_progress_delayed()

    assert mode._pending_save is True
    assert len(mode._after_jobs) == 1


def test_save_progress_delayed_cancels_previous_job(mode):
    """连续调用 _save_progress_delayed 会取消上一个 after job。"""
    mode._save_progress_delayed()
    first_job = mode._after_jobs[0]

    mode._save_progress_delayed()
    second_job = mode._after_jobs[0]

    # 旧的 job 应被取消
    assert first_job != second_job
    assert len(mode._after_jobs) == 1


def test_do_save_progress_resets_pending_on_success(mode):
    """_do_save_progress 成功时 _pending_save 重置为 False。"""
    mode._pending_save = True
    mode._do_save_progress()

    assert mode._pending_save is False
    mode.app_state.save_safe.assert_called_once()


def test_do_save_progress_keeps_pending_on_failure(monkeypatch, mode):
    """P2-16: 保存失败时 _pending_save 应保持 True，以便下次 flush 重试。"""
    mode.app_state.save_safe.return_value = False
    monkeypatch.setattr('tkinter.messagebox.showwarning', lambda *a, **k: None)

    mode._pending_save = True
    mode._do_save_progress()

    assert mode._pending_save is True
    mode.app_state.save_safe.assert_called_once()


def test_flush_pending_save_clears_pending_on_success(mode):
    """flush_pending_save 在保存成功后清空 _pending_save。"""
    mode._save_progress_delayed()
    mode.flush_pending_save()

    assert mode._pending_save is False
    assert mode._after_jobs == []


def test_flush_pending_save_keeps_pending_on_failure(monkeypatch, mode):
    """P2-16: flush_pending_save 保存失败时 _pending_save 应保持 True。"""
    mode.app_state.save_safe.return_value = False
    monkeypatch.setattr('tkinter.messagebox.showwarning', lambda *a, **k: None)

    mode._save_progress_delayed()
    mode.flush_pending_save()

    assert mode._pending_save is True
    assert mode._after_jobs == []


def test_flush_pending_save_no_op_when_not_pending(mode):
    """没有待保存时 flush_pending_save 不调用 save_safe。"""
    mode.flush_pending_save()

    assert mode._pending_save is False
    mode.app_state.save_safe.assert_not_called()


def test_destroy_calls_flush_pending_save(root, monkeypatch):
    """destroy() 会触发 flush_pending_save 以强制落盘。"""
    monkeypatch.setattr('ui.base_mode.AppState', _MockAppState)
    mode = _TestMode(root, [], MagicMock(), {})
    mode.pack()
    mode._save_progress_delayed()

    mode.destroy()

    mode.app_state.save_safe.assert_called_once()
