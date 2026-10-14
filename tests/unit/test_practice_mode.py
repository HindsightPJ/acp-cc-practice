"""practice_mode.py 单元测试（PySide6 版）。

覆盖：提交/导航触发的防抖保存、快照先行同步（进度恢复数据源）、
快照恢复（重启续练）、重新开始确认与 shuffle 回滚、保存失败子类文案。
"""

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QMessageBox

from app_state import AppState
from models import Option, Question
from ui.practice_mode import PracticeMode

pytestmark = pytest.mark.gui


def _make_question(number: int) -> Question:
    return Question(
        number=number,
        content=f"题 {number}",
        options=[Option("A", "选项 A"), Option("B", "选项 B")],
        answer="A",
    )


class _MockAppState(AppState):
    """真实 AppState 逻辑 + mock 落盘（save_safe 返回值可控）。"""

    def __init__(self) -> None:
        super().__init__(MagicMock(), progress={})
        self.save_safe = MagicMock(return_value=True)


@pytest.fixture
def state():
    return _MockAppState()


@pytest.fixture
def mode(qtbot, state):
    m = PracticeMode([_make_question(1), _make_question(2)], state)
    qtbot.addWidget(m)
    return m


def _answer_first(mode) -> None:
    """在当前题（题 1）选中 A 并提交。"""
    mode.panel.handle_option_click("A")
    mode.panel.submit_answer()


# ---------- 提交触发防抖保存 ----------


def test_panel_submit_triggers_delayed_save(mode, state):
    """P0 回归：panel 提交必须触发防抖保存且快照先行同步。"""
    _answer_first(mode)

    assert mode._pending_save is True
    assert mode._save_timer.isActive()
    # 快照已同步进 AppState（不等防抖到期——进度恢复的数据源）
    snapshot = state.get_practice_progress()
    assert snapshot["queue"] == [1, 2]
    assert snapshot["index"] == 0
    assert snapshot["answers"] == {"0": "A"}


def test_panel_navigate_triggers_delayed_save(mode, state):
    """切题后导航钩子触发防抖保存（练习位置持久化）。"""
    mode.panel.next_question()

    assert mode._pending_save is True
    assert state.get_practice_progress()["index"] == 1


def test_mode_on_submit_delegates_to_panel(mode):
    """Enter 快捷键鸭子入口 on_submit 委托 panel 提交。"""
    mode.panel.handle_option_click("A")

    mode.on_submit()

    assert mode.session.is_answered is True
    assert mode._pending_save is True


def test_submit_records_wrong_question_and_stats(mode, state):
    """答错写入错题本、统计经 AppState 递增（真实 AppState 链路）。"""
    mode.panel.handle_option_click("B")
    mode.panel.submit_answer()

    assert state.is_wrong_question(1) is True
    assert state.get_practice_stats() == {"correct": 0, "wrong": 1, "total": 1}


# ---------- 快照恢复 ----------


def test_restore_session_from_snapshot(qtbot, state):
    """重启后从 practice_progress 快照恢复队列/位置/作答。"""
    mode1 = PracticeMode([_make_question(1), _make_question(2)], state)
    qtbot.addWidget(mode1)
    mode1.panel.handle_option_click("A")
    mode1.panel.submit_answer()
    mode1.panel.next_question()
    # set_practice_progress 已在提交/导航钩子中同步快照（内存态）
    snapshot = state.get_practice_progress()
    assert snapshot["answers"] == {"0": "A"}

    mode2 = PracticeMode([_make_question(1), _make_question(2)], state)

    assert mode2.engine.get_current_index() == 1
    # 已提交记录经快照重放保存在 engine（答题卡 done 态数据源）
    assert mode2.engine.is_answered(0) is True
    assert mode2.session.is_answered is False  # 当前题未提交


def test_restore_skipped_when_snapshot_invalid(qtbot, state):
    """快照损坏（题号缺失）时回退全新会话，不抛异常。"""
    state.set_practice_progress({"queue": [99], "index": 0, "answers": {}})

    mode = PracticeMode([_make_question(1)], state)
    qtbot.addWidget(mode)

    assert mode.engine.get_current_index() == 0
    assert mode.engine.has_answers() is False


# ---------- 重新开始 ----------


def test_start_new_session_with_answers_requires_confirmation(mode, monkeypatch):
    """已有作答时重新开始必须确认；确认后清空作答。"""
    _answer_first(mode)

    # 默认 question 返回 No → 取消，作答保留
    mode.start_new_session()
    assert mode.engine.has_answers() is True

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    mode.start_new_session()
    assert mode.engine.has_answers() is False
    assert mode.engine.get_current_index() == 0


def test_start_new_session_cancel_rolls_back_shuffle(mode):
    """取消重新开始时，shuffle 复选框回滚到实际生效状态。"""
    _answer_first(mode)

    mode.shuffle_check.setChecked(True)  # 用户想开随机（仅 UI 态）
    mode.start_new_session()  # question 默认 No → 取消

    assert mode.shuffle_check.isChecked() is False  # 回滚到 _applied_shuffle
    assert mode._applied_shuffle is False


def test_start_new_session_applies_shuffle(mode, monkeypatch):
    """确认重新开始后 shuffle 生效并记录 applied 状态。"""
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    mode.shuffle_check.setChecked(True)

    mode.start_new_session()

    assert mode._applied_shuffle is True
    assert mode._pending_save is True


# ---------- 保存失败文案 ----------


def test_save_failure_message_is_practice_specific(mode, monkeypatch):
    """PracticeMode 的保存失败提示使用子类文案。"""
    mode.app_state.save_safe.return_value = False
    warned = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warned.append(k))

    mode._pending_save = True
    mode._do_save_progress()

    assert "学习进度" in mode._save_failure_message
    assert len(warned) == 1


# ---------- 主窗口协议 ----------


def test_nav_count_and_modeline(mode):
    """nav_count = 位置/总数；modeline 含 PRACTICE 段与正确率。"""
    assert mode.nav_count() == "1/2"
    _answer_first(mode)

    assert "PRACTICE" in mode.modeline_text()
    assert "100%" in mode.modeline_text()
