"""base_mode.py 单元测试（P2-20）。

覆盖 BaseMode 提取到基类的防抖保存三件套行为，
避免 P2-16 类 bug（保存失败时 _pending_save 被提前清空）回归。
"""

import tkinter as tk
from unittest.mock import MagicMock

import pytest

from ui.base_mode import BaseMode

pytestmark = pytest.mark.gui


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
def mode(root):
    """提供一个已初始化的 _TestMode 实例。"""
    state = _MockAppState(MagicMock(), {})
    widget = _TestMode(root, [], MagicMock(), state)
    widget.pack()
    yield widget
    # teardown: 取消未执行的 after 回调并清空 pending 标记，
    # 避免 destroy() 触发 flush_pending_save 时因 mock save_safe=False 而弹窗阻塞。
    widget._cancel_all_after_jobs()
    widget._pending_save = False
    try:
        widget.destroy()
    except tk.TclError:
        pass


def test_save_progress_delayed_sets_pending_flag_and_schedules_job(mode):
    """调用 _save_progress_delayed 后 _pending_save=True 且 _save_job_id 非空。"""
    assert not mode._pending_save
    assert mode._save_job_id is None

    mode._save_progress_delayed()

    assert mode._pending_save is True
    assert mode._save_job_id is not None


def test_save_progress_delayed_cancels_previous_job(mode):
    """连续调用 _save_progress_delayed 会取消上一个 after job。"""
    mode._save_progress_delayed()
    first_job = mode._save_job_id

    mode._save_progress_delayed()
    second_job = mode._save_job_id

    # 旧的 job 应被取消
    assert first_job != second_job
    assert mode._save_job_id is not None


def test_do_save_progress_resets_pending_on_success(mode):
    """_do_save_progress 成功时 _pending_save 重置为 False。"""
    mode._pending_save = True
    mode._do_save_progress()

    assert mode._pending_save is False
    mode.app_state.save_safe.assert_called_once()


def test_do_save_progress_keeps_pending_on_failure(monkeypatch, mode):
    """P2-16: 保存失败时 _pending_save 应保持 True，以便下次 flush 重试。"""
    mode.app_state.save_safe.return_value = False
    monkeypatch.setattr("tkinter.messagebox.showwarning", lambda *a, **k: None)

    mode._pending_save = True
    mode._do_save_progress()

    assert mode._pending_save is True
    mode.app_state.save_safe.assert_called_once()


def test_flush_pending_save_clears_pending_on_success(mode):
    """flush_pending_save 在保存成功后清空 _pending_save。"""
    mode._save_progress_delayed()
    mode.flush_pending_save()

    assert mode._pending_save is False
    assert len(mode._after_jobs) == 0


def test_flush_pending_save_keeps_pending_on_failure(monkeypatch, mode):
    """P2-16: flush_pending_save 保存失败时 _pending_save 应保持 True。"""
    mode.app_state.save_safe.return_value = False
    monkeypatch.setattr("tkinter.messagebox.showwarning", lambda *a, **k: None)

    mode._save_progress_delayed()
    mode.flush_pending_save()

    assert mode._pending_save is True
    assert len(mode._after_jobs) == 0


def test_flush_pending_save_no_op_when_not_pending(mode):
    """没有待保存时 flush_pending_save 不调用 save_safe。"""
    mode.flush_pending_save()

    assert mode._pending_save is False
    mode.app_state.save_safe.assert_not_called()


def test_cancel_after_job_removes_from_tracking_set(mode):
    """P0-5 回归测试：_cancel_after_job 必须从 _after_jobs 移除，避免集合累积。

    此前 ReviewMode._auto_show_job_id 在 load_question 中 after_cancel 后
    未从 _after_jobs 移除，长时间使用导致列表/set 无限增长。
    """
    job_id = mode.after(5000, lambda: None)  # 永不执行的占位任务
    mode._add_after_job(job_id)
    assert job_id in mode._after_jobs
    assert len(mode._after_jobs) == 1

    mode._cancel_after_job(job_id)

    assert job_id not in mode._after_jobs
    assert len(mode._after_jobs) == 0


def test_cancel_after_job_none_is_noop(mode):
    """P0-5: _cancel_after_job(None) 应安全返回，不抛异常。"""
    # 调用方常传可空变量（如 self._auto_show_job_id），None 时应直接返回
    mode._cancel_after_job(None)
    assert len(mode._after_jobs) == 0


def test_cancel_after_job_idempotent(mode):
    """P0-5: 对同一 job_id 重复调用 _cancel_after_job 不抛异常。"""
    job_id = mode.after(5000, lambda: None)
    mode._add_after_job(job_id)

    mode._cancel_after_job(job_id)
    mode._cancel_after_job(job_id)  # 重复调用应安全（discard 不抛 KeyError）

    assert len(mode._after_jobs) == 0


def test_add_after_job_dedup(mode):
    """P0-5: 重复添加同一 job_id 不会产生重复条目（set 自动去重）。"""
    job_id = mode.after(5000, lambda: None)

    mode._add_after_job(job_id)
    mode._add_after_job(job_id)  # 重复添加

    assert len(mode._after_jobs) == 1


def test_destroy_calls_flush_pending_save(root):
    """destroy() 会触发 flush_pending_save 以强制落盘。"""
    state = _MockAppState(MagicMock(), {})
    mode = _TestMode(root, [], MagicMock(), state)
    mode.pack()
    mode._save_progress_delayed()

    mode.destroy()

    mode.app_state.save_safe.assert_called_once()
