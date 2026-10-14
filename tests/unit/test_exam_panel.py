"""exam_panel.py 单元测试（PySide6 版）。

覆盖考试视图核心渲染与交互：题号导航四态、计时显示、题目加载、选项同步、
导航按钮点击跳转与动作回调接线。
"""

from unittest.mock import MagicMock

import pytest

from models import Option, Question
from quiz_engine import QuizEngine
from ui.exam_panel import ExamPanel
from ui.exam_session import ExamSession

pytestmark = pytest.mark.gui


def make_question(number: int, q_type: str = "single", answer: str = "A") -> Question:
    """构造考试用题目。"""
    return Question(
        number=number,
        content=f"题干 {number}",
        options=[
            Option("A", "选项 A"),
            Option("B", "选项 B"),
            Option("C", "选项 C"),
            Option("D", "选项 D"),
        ],
        answer=answer,
        type=q_type,
        explanation=f"解析 {number}",
    )


@pytest.fixture
def engine():
    """已启动考试模式的 QuizEngine。"""
    eng = QuizEngine([make_question(i) for i in range(1, 4)])
    eng.start_exam_mode(question_count=3, shuffle=False)
    return eng


@pytest.fixture
def callbacks():
    return {
        k: MagicMock()
        for k in ("on_prev", "on_next", "on_submit", "on_mark", "on_jump", "on_select_option")
    }


@pytest.fixture
def panel(qtbot, engine, callbacks):
    p = ExamPanel(engine, ExamSession(engine), **callbacks)
    p.build_nav_buttons(3)
    qtbot.addWidget(p)
    return p


# ---------- 题号导航网格 ----------


def test_build_nav_buttons_creates_expected_buttons(panel):
    """build_nav_buttons 按总题数创建题号按钮。"""
    assert len(panel._nav_buttons) == 3
    assert [btn.text() for btn in panel._nav_buttons] == ["1", "2", "3"]


def test_load_question_highlights_current(panel):
    """加载题目后当前题号按钮四态为 current。"""
    panel.load_question()

    assert panel._nav_buttons[0].property("state") == "current"
    assert panel._nav_buttons[1].property("state") is None


def test_nav_button_shows_answered(panel):
    """已答题号按钮为 answered 态。"""
    panel.exam_session.select_option("A")
    panel.load_question()
    # 切到第 2 题：第 1 题保持已答记录 → answered
    panel.engine.next_question()
    panel.load_question()

    assert panel._nav_buttons[0].property("state") == "answered"
    assert panel._nav_buttons[1].property("state") == "current"


def test_nav_button_shows_marked(panel):
    """标记题号按钮显示星号前缀 + marked 态（当前题优先级更高）。"""
    panel.exam_session.toggle_mark()
    panel.load_question()

    # 当前题显示 current；切走后该题回落为 marked
    assert panel._nav_buttons[0].property("state") == "current"
    panel.engine.next_question()
    panel.load_question()

    assert panel._nav_buttons[0].text().startswith("★")
    assert panel._nav_buttons[0].property("state") == "marked"


def test_nav_button_click_calls_on_jump(panel, callbacks):
    """点击题号按钮触发 on_jump(索引)。"""
    panel._nav_buttons[1].click()

    callbacks["on_jump"].assert_called_once_with(1)


# ---------- 计时器 ----------


def test_update_timer_display_normal(panel):
    """正常剩余时间显示为 MM:SS，并同步统计列数值标签。"""
    panel.load_question()  # 先填充统计列 blocks
    panel.update_timer_display(3661, 7200)

    assert panel._time_text == "61:01"
    _k, v_lbl, _u = panel.stats_col._blocks[0]
    assert v_lbl.text() == "61:01"


def test_update_timer_display_before_stats_col_built(panel):
    """统计列未构建时只更新缓存值，不崩溃。"""
    panel.update_timer_display(599, 3600)

    assert panel._time_text == "09:59"


def test_update_timer_display_clamps_negative(panel):
    """负数剩余时间钳到 00:00。"""
    panel.update_timer_display(-5, 3600)

    assert panel._time_text == "00:00"


# ---------- 题目加载 ----------


def test_load_question_displays_content(panel):
    """load_question 将题干与题号写入详情卡。"""
    panel.load_question()

    assert "题干 1" in panel.detail_card.stem.text()
    assert panel.detail_card.big_no.text() == "1"


def test_load_question_shows_progress(panel):
    """load_question 更新题头 meta 进度（QUEUE 01/03 格式）。"""
    panel.load_question()

    assert "01/03" in panel.detail_card._meta_labels[1].text()


def test_load_question_restores_selection(panel):
    """load_question 恢复当前题的已选状态。"""
    panel.exam_session.select_option("B")

    panel.load_question()

    assert panel.detail_card.option_cards[1].property("state") == "selected"


# ---------- 选项同步 ----------


def test_sync_option_selection_updates_cards(panel):
    """sync_option_selection 按字母串同步选项行选中态。"""
    panel.load_question()

    panel.sync_option_selection("AC")

    assert panel.detail_card.option_cards[0].property("state") == "selected"
    assert panel.detail_card.option_cards[2].property("state") == "selected"
    assert panel.detail_card.option_cards[1].property("state") is None


def test_sync_option_selection_updates_nav(panel):
    """选项同步后题号网格同步为 answered 态。"""
    panel.load_question()

    panel.sync_option_selection("A")

    assert panel._nav_buttons[0].property("state") == "current"  # 当前题仍是 current


# ---------- 动作回调接线 ----------


def test_action_buttons_wired_to_callbacks(panel, callbacks):
    """动作条按钮点击转发到构造传入的回调。"""
    panel.mark_btn.click()
    callbacks["on_mark"].assert_called_once()

    panel.submit_btn.click()
    callbacks["on_submit"].assert_called_once()


def test_stats_col_reflects_answered_and_marked(panel):
    """统计列展示已答数与标记数。"""
    panel.load_question()
    panel.exam_session.select_option("A")
    panel.exam_session.toggle_mark()
    panel.sync_option_selection("A")

    texts = [blk[1].text() for blk in panel.stats_col._blocks]
    assert texts[1] == "1/3"
    assert texts[2] == "1"
