"""exam_mode.py 单元测试（PySide6 版）。

覆盖考试编排逻辑：开考、选项选择、导航、标记、计时、交卷、历史保存、
键盘协议（on_letter/on_prev/on_next，Enter 无提交语义）。
"""

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QMessageBox

from models import Option, Question
from quiz_engine import QuizEngine
from ui.exam_mode import ExamMode

pytestmark = pytest.mark.gui


def make_question(number: int, q_type: str = "single", answer: str = "A") -> Question:
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


class _MockAppState:
    """最小 AppState 替代（ExamMode 触及的接口子集）。"""

    def __init__(self):
        self.save_safe = MagicMock(return_value=True)
        self._history: list[dict] = []
        self._wrong: set[int] = set()

    def add_exam_history(self, entry):
        self._history.append(entry)

    def get_exam_history(self):
        return list(self._history)

    def is_wrong_question(self, q_num):
        return q_num in self._wrong

    def add_wrong_question(self, q_num):
        self._wrong.add(q_num)


@pytest.fixture
def mode(qtbot, monkeypatch):
    """已静音弹窗的 ExamMode；考试抽题固定不 shuffle，combo 换小额选项。"""
    # 报告对话框为模态 exec，无头进程会永久阻塞 → 类级替换为捕获回调
    reports: list[dict] = []
    monkeypatch.setattr(ExamMode, "_show_exam_report", lambda self, report: reports.append(report))

    # 测试用小额 combo 选项（生产为 50/100/150/200，题库只有 3 题）
    monkeypatch.setattr("ui.exam_mode._COUNT_OPTIONS", ("1", "2", "3"))
    monkeypatch.setattr("ui.exam_mode._DURATION_OPTIONS", ("1", "30"))

    original_start_exam_mode = QuizEngine.start_exam_mode

    def _deterministic_start(self, question_count=100, shuffle=True):
        original_start_exam_mode(self, question_count=question_count, shuffle=False)

    monkeypatch.setattr(QuizEngine, "start_exam_mode", _deterministic_start)

    questions = [
        make_question(1),
        make_question(2),
        make_question(3, q_type="multiple", answer="AC"),
    ]
    m = ExamMode(questions, _MockAppState())
    qtbot.addWidget(m)
    return m


def _start(mode, count="3", duration="30") -> None:
    mode.count_combo.setCurrentText(count)
    mode.duration_combo.setCurrentText(duration)
    mode.start_exam()


# ---------- 开考 ----------


def test_start_exam_initializes_engine_session_panel(mode):
    """start_exam 初始化 engine、session、panel，切到考试视图并启动计时。"""
    _start(mode, count="2", duration="30")

    assert mode.engine is not None
    assert mode.exam_session is not None
    assert mode.panel is not None
    assert mode.engine.queue_length() == 2
    assert mode.timer_running is True
    assert mode._timer.isActive()
    assert mode.stack.currentIndex() == 1  # 考试视图


def test_start_exam_destroys_previous_panel(mode):
    """重复开考时旧 panel 被销毁替换（防泄漏）。"""
    _start(mode, count="2", duration="30")
    first_panel = mode.panel

    _start(mode, count="2", duration="30")

    assert mode.panel is not first_panel
    assert mode.engine.queue_length() == 2


# ---------- 选项选择 ----------


def test_select_option_updates_session_and_panel(mode):
    """选项选择更新 session 并同步 panel 选项行。"""
    _start(mode)

    mode._select_option_by_letter("A")

    assert mode.exam_session.get_current_selected() == "A"
    assert mode.panel.detail_card.option_cards[0].property("state") == "selected"
    assert mode.panel.detail_card.option_cards[1].property("state") is None


def test_select_option_toggles_multiple(mode):
    """多选题重复点击同字母为取消（toggle 语义）。"""
    _start(mode)
    mode.engine.set_current_index(2)  # 题 3 = multiple AC
    mode.panel.load_question()

    mode._select_option_by_letter("A")
    mode._select_option_by_letter("C")
    mode._select_option_by_letter("A")

    assert mode.exam_session.get_current_selected() == "C"


# ---------- 导航 ----------


def test_exam_next_and_prev(mode):
    """下一题前进 / 上一题返回。"""
    _start(mode)

    mode._exam_next_question()
    assert mode.engine.get_current_index() == 1

    mode._exam_prev_question()
    assert mode.engine.get_current_index() == 0


def test_jump_to_question_valid_and_out_of_range(mode):
    """跳转有效题号生效；越界跳转无操作。"""
    _start(mode)

    mode._jump_to_question(2)
    assert mode.engine.get_current_index() == 2

    mode._jump_to_question(99)
    assert mode.engine.get_current_index() == 2


# ---------- 标记 ----------


def test_toggle_mark_current(mode):
    """切换标记更新 session；切走后该题号网格回落 marked 态。"""
    _start(mode)

    mode._toggle_mark_current()

    assert mode.exam_session.is_marked(0) is True
    # 当前题显示 current（优先级更高），切到下一题后标记态显现
    mode._exam_next_question()
    assert mode.panel._nav_buttons[0].property("state") == "marked"
    assert mode.panel._nav_buttons[0].text().startswith("★")


# ---------- 计时器 ----------


def test_timer_tick_updates_remaining(mode, monkeypatch):
    """tick 后剩余时间按 engine 已耗时长重新计算并刷新面板。"""
    _start(mode, count="3", duration="30")
    assert mode._timer.isActive()

    mode._on_timer_tick()

    assert mode.time_remaining <= 1800
    assert mode.panel._time_text is not None


def test_timer_expiry_auto_submits(mode, monkeypatch):
    """时间到自动强制造卷（无需用户确认）。"""
    _start(mode, count="1", duration="1")
    # 模拟引擎已耗时 1 小时（远超 1 分钟时长）
    monkeypatch.setattr(mode.engine, "get_exam_elapsed_seconds", lambda: 3600)

    mode._on_timer_tick()

    assert mode.timer_running is False
    assert not mode._timer.isActive()
    assert len(mode.app_state.get_exam_history()) == 1


# ---------- 交卷 ----------


def test_submit_exam_records_answers_and_saves_history(mode, monkeypatch):
    """确认交卷后记录答案、保存历史并展示报告。"""
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    _start(mode, count="2", duration="30")

    mode._select_option_by_letter("A")  # 题 1 正确
    mode._exam_next_question()
    mode._select_option_by_letter("B")  # 题 2 正确
    mode.submit_exam()

    assert mode.timer_running is False
    history = mode.app_state.get_exam_history()
    assert len(history) == 1
    assert history[0]["total_questions"] == 2
    assert history[0]["correct"] + history[0]["wrong"] == 2


def test_submit_exam_canceled_keeps_running(mode):
    """用户取消交卷（question 返回 No 默认）不保存历史、继续计时。"""
    _start(mode, count="1", duration="30")

    mode.submit_exam()

    assert len(mode.app_state.get_exam_history()) == 0
    assert mode.timer_running is True


def test_submit_exam_force_bypasses_confirmation(mode):
    """force=True 跳过确认直接交卷。"""
    _start(mode, count="1", duration="30")

    mode.submit_exam(force=True)

    assert len(mode.app_state.get_exam_history()) == 1


def test_submit_exam_resets_ui(mode):
    """交卷后 panel 清理、回设置视图、开始按钮恢复。"""
    _start(mode, count="1", duration="30")

    mode.submit_exam(force=True)

    assert mode.panel is None
    assert mode.stack.currentIndex() == 0
    assert mode.start_btn.isEnabled()


def test_add_report_wrong_deduplicates(mode):
    """报告"加入错题本"回调按题号去重，返回新增数量。"""
    report = {"wrong_questions": [make_question(1), make_question(1), make_question(2)]}

    added = mode._add_report_wrong(report)

    assert added == 2
    assert mode.app_state.is_wrong_question(1) is True
    assert mode.app_state.is_wrong_question(2) is True

    # 重复加入：全部已存在 → 新增 0
    assert mode._add_report_wrong(report) == 0


# ---------- 键盘协议 ----------


def test_on_letter_selects_option_in_exam_view(mode):
    """考试视图中 A-D 切换选项。"""
    _start(mode)

    mode.on_letter("A")

    assert mode.exam_session.get_current_selected() == "A"


def test_on_letter_ignored_in_settings_view(mode):
    """设置视图中按键无语义（不建引擎）。"""
    mode.on_letter("A")

    assert mode.engine is None


def test_on_submit_has_no_semantics(mode):
    """考试模式 Enter 无提交动作（交卷仅按钮触发，防误交卷）。"""
    _start(mode, count="2", duration="30")

    mode.on_submit()

    assert len(mode.app_state.get_exam_history()) == 0
    assert mode.timer_running is True


def test_on_prev_next_route_in_exam_view(mode):
    """←/→ 快捷键鸭子转发到翻题。"""
    _start(mode)

    mode.on_next()
    assert mode.engine.get_current_index() == 1

    mode.on_prev()
    assert mode.engine.get_current_index() == 0


# ---------- 导航计数 ----------


def test_nav_count_reflects_answered(mode):
    """考试中 board-nav 计数 = 已答/总数；未开考为 None。"""
    assert mode.nav_count() is None

    _start(mode, count="3", duration="30")
    mode._select_option_by_letter("A")

    assert mode.nav_count() == "1/3"
