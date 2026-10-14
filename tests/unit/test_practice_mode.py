"""practice_mode.py 单元测试（P2-21）。

覆盖练习提交后的延迟保存触发、子类 _save_failure_message 生效、
P0 回归（panel 提交路径必须触发防抖保存）与快照同步。
"""

from unittest.mock import MagicMock

import pytest

from app_state import AppState
from models import Question, Option
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
def mode(root):
    """提供一个已初始化的 PracticeMode 实例。"""
    state = _MockAppState()
    questions = [_make_question(1), _make_question(2)]
    mode = PracticeMode(root, questions, MagicMock(), state)
    mode.pack()
    yield mode
    # 清理：重置 save_safe 与 _pending_save，避免 destroy → flush_pending_save
    # 触发真实 messagebox.showwarning 阻塞测试（monkeypatch 已在此时撤销）
    mode.app_state.save_safe.return_value = True
    mode._pending_save = False
    mode.destroy()


def _select_first_option(mode) -> None:
    """在当前题上选中 A（走 panel 的真实点击路径）。"""
    question = mode.session.engine.get_current_question()
    mode.session.get_question_type(question)
    mode.panel.handle_option_click("A")


def test_panel_submit_triggers_delayed_save(mode):
    """P0 回归：经 panel 提交（按钮/键盘同一入口）必须触发防抖保存。

    回归背景：PracticePanel 构造未接线 on_submit 时，_save_progress_delayed
    的唯一入口（PracticeMode.submit_answer 包装器）无生产调用方，练习进度
    永不落盘。修复后 panel 提交完成统一触发 _on_answer_submitted 钩子。
    """
    _select_first_option(mode)
    mode.panel.submit_answer()

    assert mode._pending_save is True
    assert mode._save_job_id is not None
    # 快照已同步进 AppState（进度恢复的数据源）
    snapshot = mode.app_state.get_practice_progress()
    assert snapshot["queue"] == [1, 2]
    assert snapshot["index"] == 0
    assert snapshot["answers"] == {"0": "A"}


def test_panel_navigate_triggers_delayed_save(mode):
    """切题后导航钩子应触发防抖保存（练习位置持久化）。"""
    mode.panel.next_question()

    assert mode._pending_save is True
    assert mode.app_state.get_practice_progress()["index"] == 1


def test_mode_submit_answer_delegates_to_panel(mode):
    """兼容入口 submit_answer 应委托 panel 提交并触发保存。"""
    _select_first_option(mode)
    mode.submit_answer()

    assert mode.session.is_answered is True
    assert mode._pending_save is True


def test_save_failure_message_is_practice_specific(mode, monkeypatch):
    """PracticeMode 的保存失败提示应使用子类文案。"""
    mode.app_state.save_safe.return_value = False
    monkeypatch.setattr("tkinter.messagebox.showwarning", lambda *a, **k: None)

    mode._pending_save = True
    mode._do_save_progress()

    # 文案应包含"学习进度"（子类覆盖的 _save_failure_message）
    assert "学习进度" in mode._save_failure_message
