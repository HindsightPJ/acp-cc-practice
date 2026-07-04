"""exam_mode.py 单元测试。

覆盖考试模式编排逻辑：启动考试、选项选择、导航、交卷、计时器、历史保存。
"""
from unittest.mock import MagicMock, patch

import tkinter as tk
import pytest

from models import Question, Option
from quiz_engine import QuizEngine
from ui.exam_mode import ExamMode

pytestmark = pytest.mark.gui


# ---------- 辅助函数 / fixtures ----------

def make_question(number: int, q_type: str = 'single', answer: str = 'A') -> Question:
    return Question(
        number=number,
        content=f'题干 {number}',
        options=[
            Option('A', '选项 A'),
            Option('B', '选项 B'),
            Option('C', '选项 C'),
            Option('D', '选项 D'),
        ],
        answer=answer,
        type=q_type,
        explanation=f'解析 {number}',
    )


class _MockAppState:
    """最小 AppState 替代。"""

    def __init__(self, data_manager, progress):
        self.save_safe = MagicMock(return_value=True)
        self._history = []
        self._wrong = set()

    def add_exam_history(self, entry):
        self._history.append(entry)

    def get_exam_history(self):
        return list(self._history)

    def is_wrong_question(self, q_num):
        return q_num in self._wrong

    def add_wrong_question(self, q_num):
        self._wrong.add(q_num)


@pytest.fixture
def mode(root, monkeypatch):
    """提供一个已初始化的 ExamMode 实例。"""
    state = _MockAppState(MagicMock(), {})
    monkeypatch.setattr('tkinter.messagebox.showinfo', lambda *a, **k: None)
    monkeypatch.setattr('tkinter.messagebox.showwarning', lambda *a, **k: None)
    monkeypatch.setattr('tkinter.messagebox.showerror', lambda *a, **k: None)

    # 测试用固定题目顺序，避免随机 shuffle 导致断言不稳定
    original_start_exam_mode = QuizEngine.start_exam_mode

    def _deterministic_start_exam_mode(self, question_count=100, shuffle=True):
        original_start_exam_mode(self, question_count=question_count, shuffle=False)

    monkeypatch.setattr(QuizEngine, 'start_exam_mode', _deterministic_start_exam_mode)

    questions = [make_question(1), make_question(2), make_question(3, q_type='multiple', answer='AC')]
    m = ExamMode(root, questions, MagicMock(), state)
    m.pack()
    yield m
    try:
        m.destroy()
    except tk.TclError:
        pass


# ---------- 启动考试 ----------

def test_start_exam_initializes_engine_and_session(mode):
    """start_exam 初始化 engine、session 和 panel。"""
    mode.question_count_var.set('2')
    mode.duration_var.set('30')
    mode.start_exam()

    assert mode.engine is not None
    assert mode.exam_session is not None
    assert mode.panel is not None
    assert mode.engine.queue_length() == 2
    assert mode.timer_running is True
    assert mode.start_btn.cget('state') == tk.DISABLED


def test_start_exam_invalid_input_shows_error(root, monkeypatch):
    """输入非法数值时弹出错误且不启动考试。"""
    state = _MockAppState(MagicMock(), {})
    monkeypatch.setattr('tkinter.messagebox.showerror', lambda *a, **k: None)
    m = ExamMode(root, [make_question(1)], MagicMock(), state)
    m.question_count_var.set('abc')
    m.duration_var.set('60')

    m.start_exam()

    assert m.engine is None
    m.destroy()


# ---------- 选项选择 ----------

def test_exam_select_option_updates_session_and_panel(mode):
    """选项选择编排更新 session 并同步 panel。"""
    mode.question_count_var.set('3')
    mode.duration_var.set('30')
    mode.start_exam()

    mode.exam_select_option_by_letter('A')

    assert mode.exam_session.get_current_selected() == 'A'
    # panel 实际控件状态应反映选择
    assert mode.panel.exam_option_cards[0]['row'].is_selected is True


# ---------- 导航 ----------

def test_exam_next_question_advances(mode):
    """下一题前进到下一题。"""
    mode.question_count_var.set('3')
    mode.duration_var.set('30')
    mode.start_exam()

    mode.exam_next_question()
    assert mode.engine.get_current_index() == 1


def test_exam_prev_question_goes_back(mode):
    """上一题返回到上一题。"""
    mode.question_count_var.set('3')
    mode.duration_var.set('30')
    mode.start_exam()
    mode.engine.next_question()

    mode.exam_prev_question()
    assert mode.engine.get_current_index() == 0


def test_jump_to_question_valid(mode):
    """跳转到有效题号。"""
    mode.question_count_var.set('3')
    mode.duration_var.set('30')
    mode.start_exam()

    mode.jump_to_question(2)
    assert mode.engine.get_current_index() == 2


def test_jump_to_question_out_of_range_is_noop(mode):
    """跳转到无效题号无操作。"""
    mode.question_count_var.set('3')
    mode.duration_var.set('30')
    mode.start_exam()

    mode.jump_to_question(99)
    assert mode.engine.get_current_index() == 0


# ---------- 标记 ----------

def test_toggle_mark_current_updates_session_and_panel(mode):
    """切换标记更新 session 和题号导航。"""
    mode.question_count_var.set('3')
    mode.duration_var.set('30')
    mode.start_exam()

    mode.toggle_mark_current()
    assert mode.exam_session.is_marked(0) is True


# ---------- 计时器 ----------

def test_update_timer_updates_display_and_schedules_next(mode):
    """update_timer 更新计时器显示并安排下一次回调。"""
    mode.question_count_var.set('1')
    mode.duration_var.set('1')
    mode.start_exam()

    old_job_id = mode._timer_job_id
    old_time = mode.time_remaining
    mode.update_timer()

    # 计时器标签应被刷新（时间减少或至少 job id 已更新）
    assert mode._timer_job_id is not None
    assert mode._timer_job_id != old_job_id or mode.time_remaining != old_time


# ---------- 交卷 ----------

def test_submit_exam_records_answers_and_saves_history(mode, monkeypatch):
    """交卷后记录答案、保存历史并展示报告。"""
    monkeypatch.setattr('tkinter.messagebox.askyesno', lambda *a, **k: True)
    mode.question_count_var.set('2')
    mode.duration_var.set('30')
    mode.start_exam()

    # 答题
    mode.exam_select_option_by_letter('A')  # 题 1 正确
    mode.exam_next_question()
    mode.exam_select_option_by_letter('B')  # 题 2 正确

    with patch('ui.exam_mode.ExamReportDialog') as mock_dialog:
        mode.submit_exam()
        mock_dialog.assert_called_once()

    assert mode.timer_running is False
    assert len(mode.app_state.get_exam_history()) == 1
    history = mode.app_state.get_exam_history()[0]
    assert history['total_questions'] == 2
    assert history['correct'] + history['wrong'] == history['total_questions']


def test_submit_exam_canceled_by_user_does_not_submit(mode, monkeypatch):
    """用户取消交卷时不保存历史。"""
    monkeypatch.setattr('tkinter.messagebox.askyesno', lambda *a, **k: False)
    mode.question_count_var.set('1')
    mode.duration_var.set('30')
    mode.start_exam()

    mode.submit_exam()

    assert len(mode.app_state.get_exam_history()) == 0
    assert mode.timer_running is True


def test_submit_exam_force_bypasses_confirmation(mode, monkeypatch):
    """force=True 时跳过确认弹窗。"""
    mode.question_count_var.set('1')
    mode.duration_var.set('30')
    mode.start_exam()

    with patch('ui.exam_mode.ExamReportDialog'):
        mode.submit_exam(force=True)

    assert len(mode.app_state.get_exam_history()) == 1


def test_submit_exam_resets_ui(mode, monkeypatch):
    """交卷后恢复开始按钮并清理 panel。"""
    monkeypatch.setattr('tkinter.messagebox.askyesno', lambda *a, **k: True)
    mode.question_count_var.set('1')
    mode.duration_var.set('30')
    mode.start_exam()

    with patch('ui.exam_mode.ExamReportDialog'):
        mode.submit_exam()

    assert mode.panel is None
    assert mode.start_btn.cget('state') == tk.NORMAL


# ---------- 键盘分发 ----------

def test_on_key_press_option_key_selects_option(mode):
    """选项字母键通过基类方法触发选择。"""
    mode.question_count_var.set('1')
    mode.duration_var.set('30')
    mode.start_exam()

    event = MagicMock()
    event.keysym = 'a'
    event.char = 'a'
    result = mode._on_key_press(event)

    assert result == 'break'
    assert mode.exam_session.get_current_selected() == 'A'


def test_on_key_press_left_delegates_to_panel(mode):
    """Left 键委托 panel 处理并触发上一题。"""
    mode.question_count_var.set('2')
    mode.duration_var.set('30')
    mode.start_exam()
    mode.engine.next_question()

    event = MagicMock()
    event.keysym = 'Left'
    event.char = ''
    result = mode._on_key_press(event)

    assert result == 'break'
    assert mode.engine.get_current_index() == 0
