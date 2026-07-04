"""exam_panel.py 单元测试。

覆盖考试视图核心渲染与交互：题号导航、计时器、题目加载、选项同步、跳转校验。
"""
from unittest.mock import MagicMock

import tkinter as tk
import pytest

from models import Question, Option
from quiz_engine import QuizEngine
from ui.exam_panel import ExamPanel
from ui.exam_session import ExamSession

pytestmark = pytest.mark.gui


# ---------- 辅助函数 ----------

def make_question(number: int, q_type: str = 'single', answer: str = 'A') -> Question:
    """构造考试用题目。"""
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


@pytest.fixture
def engine():
    """已启动考试模式的 QuizEngine。"""
    questions = [make_question(i) for i in range(1, 4)]
    eng = QuizEngine(questions)
    eng.start_exam_mode(question_count=len(questions), shuffle=False)
    return eng


@pytest.fixture
def panel(root, engine):
    """构建 ExamPanel 实例。"""
    session = ExamSession(engine)
    callbacks = {k: MagicMock() for k in ['on_prev', 'on_next', 'on_submit', 'on_mark', 'on_jump', 'on_select_option']}
    p = ExamPanel(
        root,
        engine=engine,
        exam_session=session,
        **callbacks,
    )
    p.pack(fill=tk.BOTH, expand=True)
    root.update_idletasks()
    yield p
    try:
        p.destroy()
    except tk.TclError:
        pass


# ---------- 题号导航 ----------

def test_build_nav_buttons_creates_expected_buttons(panel):
    """build_nav_buttons 按总题数创建题号按钮。"""
    panel.build_nav_buttons(3)
    assert len(panel.nav_buttons) == 3
    texts = [btn.cget('text') for btn in panel.nav_buttons]
    assert texts == ['1', '2', '3']


def test_update_nav_buttons_highlights_current(panel, engine):
    """update_nav_buttons 高亮当前题号。"""
    panel.build_nav_buttons(3)
    panel.update_nav_buttons()
    current_bg = panel.nav_buttons[0].cget('bg')
    other_bg = panel.nav_buttons[1].cget('bg')
    assert current_bg != other_bg


def test_update_nav_buttons_shows_answered(panel, engine):
    """已答题的题号按钮应显示绿色背景。"""
    panel.build_nav_buttons(3)
    panel.exam_session.select_option('A')
    panel.update_nav_buttons()
    answered_bg = panel.nav_buttons[0].cget('bg')
    unanswered_bg = panel.nav_buttons[1].cget('bg')
    assert answered_bg != unanswered_bg


def test_update_nav_buttons_shows_marked(panel, engine):
    """标记题号应显示星号前缀。"""
    panel.build_nav_buttons(3)
    panel.exam_session.toggle_mark()
    panel.update_nav_buttons()
    assert '★' in panel.nav_buttons[0].cget('text')


# ---------- 计时器 ----------

def test_update_timer_display_normal(panel):
    """正常剩余时间显示为 MM:SS。"""
    panel.update_timer_display(3661, 7200)
    assert panel.timer_label.cget('text') == '61:01'


def test_update_timer_display_last_five_minutes(panel):
    """剩余 5 分钟内标签颜色会随秒数切换。"""
    panel.update_timer_display(300, 3600)
    assert panel.timer_label.cget('text') == '05:00'
    color_even = panel.timer_label.cget('fg')
    panel.update_timer_display(299, 3600)
    color_odd = panel.timer_label.cget('fg')
    assert color_even != color_odd


# ---------- 题目加载 ----------

def test_load_question_displays_content(panel, engine):
    """load_question 将当前题干写入文本框。"""
    panel.load_question()
    text = panel.exam_question_text.get('1.0', tk.END)
    assert '题干 1' in text


def test_load_question_shows_progress(panel, engine):
    """load_question 更新进度标签。"""
    panel.load_question()
    assert '1 / 3' in panel.exam_progress_label.cget('text')


def test_load_question_restores_selection(panel, engine):
    """load_question 恢复当前题的已选状态。"""
    panel.exam_session.select_option('B')
    panel.load_question()
    assert panel.exam_option_cards[1]['row'].is_selected is True


# ---------- 选项同步 ----------

def test_sync_option_selection_updates_ui(panel, engine):
    """sync_option_selection 根据字母串更新选项 UI。"""
    panel.load_question()
    panel.sync_option_selection('AC')
    assert panel.exam_option_cards[0]['row'].is_selected is True
    assert panel.exam_option_cards[2]['row'].is_selected is True
    assert panel.exam_option_cards[1]['row'].is_selected is False


def test_sync_option_selection_handles_none_engine(panel):
    """engine 为 None 时 sync_option_selection 不崩溃。"""
    panel.engine = None
    panel.sync_option_selection('AC')  # 不应抛出异常


# ---------- 键盘与交互 ----------

def test_handle_key_press_left_calls_prev(panel):
    """Left 键触发 on_prev 回调。"""
    event = MagicMock()
    event.keysym = 'Left'
    event.char = ''
    panel.handle_key_press(event)
    panel._on_prev.assert_called_once()


def test_handle_key_press_right_calls_next(panel):
    """Right 键触发 on_next 回调。"""
    event = MagicMock()
    event.keysym = 'Right'
    event.char = ''
    panel.handle_key_press(event)
    panel._on_next.assert_called_once()


def test_handle_key_press_m_calls_mark(panel):
    """M 键触发 on_mark 回调。"""
    event = MagicMock()
    event.keysym = 'm'
    event.char = 'm'
    panel.handle_key_press(event)
    panel._on_mark.assert_called_once()


def test_on_jump_entry_valid_number(panel):
    """跳转输入有效题号时触发 on_jump。"""
    panel.jump_var.set('2')
    panel._on_jump_entry()
    panel._on_jump.assert_called_once_with(1)


def test_on_jump_entry_invalid_number(panel, monkeypatch):
    """跳转输入非数字时弹出错误且不触发 on_jump。"""
    monkeypatch.setattr('tkinter.messagebox.showerror', lambda *a, **k: None)
    panel.jump_var.set('abc')
    panel._on_jump_entry()
    panel._on_jump.assert_not_called()


def test_on_jump_entry_out_of_range(panel, monkeypatch):
    """跳转输入超出范围时弹出错误且不触发 on_jump。"""
    monkeypatch.setattr('tkinter.messagebox.showerror', lambda *a, **k: None)
    panel.jump_var.set('99')
    panel._on_jump_entry()
    panel._on_jump.assert_not_called()
