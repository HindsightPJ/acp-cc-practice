"""practice_mode.py 单元测试（P2-21）。

覆盖练习提交后的延迟保存触发、子类 _save_failure_message 生效等。
"""
import tkinter as tk
from unittest.mock import MagicMock, patch

import pytest

from models import Question
from ui.practice_mode import PracticeMode


def _make_question(number: int) -> Question:
    return Question(number=number, content=f"题 {number}", answer="A")


class _MockAppState:
    """最小 AppState 替代。"""

    def __init__(self, data_manager, progress):
        self.save_safe = MagicMock(return_value=True)


@pytest.fixture(scope='module')
def root():
    """模块级共享 Tk 实例。"""
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


@pytest.fixture
def mode(root, monkeypatch):
    """提供一个已初始化的 PracticeMode 实例。"""
    monkeypatch.setattr('ui.base_mode.AppState', _MockAppState)
    questions = [_make_question(1), _make_question(2)]
    mode = PracticeMode(root, questions, MagicMock(), {})
    mode.pack()
    yield mode
    mode.destroy()


def test_submit_answer_triggers_delayed_save(mode):
    """PracticeMode.submit_answer 应触发延迟保存。"""
    # mock 面板提交，避免依赖 PracticePanel 的完整行为
    with patch.object(mode.panel, 'submit_answer'):
        mode.submit_answer()

    assert mode._pending_save is True
    assert len(mode._after_jobs) == 1


def test_save_failure_message_is_practice_specific(mode, monkeypatch):
    """PracticeMode 的保存失败提示应使用子类文案。"""
    mode.app_state.save_safe.return_value = False
    monkeypatch.setattr('tkinter.messagebox.showwarning', lambda *a, **k: None)

    mode._pending_save = True
    mode._do_save_progress()

    # 文案应包含"学习进度"（子类覆盖的 _save_failure_message）
    assert '学习进度' in mode._save_failure_message
