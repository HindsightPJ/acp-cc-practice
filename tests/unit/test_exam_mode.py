"""exam_mode.py 单元测试（PySide6 版）。

覆盖考试编排逻辑：开考、选项选择、导航、标记、计时、交卷、历史保存、
键盘协议（on_letter/on_prev/on_next，Enter 无提交语义）。
"""

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QLabel, QMessageBox

from app_state import AppState
from models import Option, Question
from ui.exam_mode import ExamMode
from ui.option_row import OptionRow

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


class _FakeDataManager:
    def __init__(self) -> None:
        self.saved: dict | None = None

    def save_progress(self, progress: dict) -> None:
        self.saved = progress


class _MockAppState(AppState):
    """内存版 AppState：卡组/历史/错题走真实逻辑，save_safe 打桩防落盘。"""

    def __init__(self) -> None:
        super().__init__(_FakeDataManager(), {})
        self.save_safe = MagicMock(return_value=True)


@pytest.fixture
def mode(qtbot, monkeypatch):
    """已静音弹窗的 ExamMode；卡组预置 [1,2,3] 保证题序确定。"""
    # 报告对话框为模态 exec，无头进程会永久阻塞 → 类级替换为捕获回调
    reports: list[dict] = []
    monkeypatch.setattr(ExamMode, "_show_exam_report", lambda self, report: reports.append(report))

    # 测试用小额 combo 选项（生产为 50/100/150/200，题库只有 3 题）
    monkeypatch.setattr("ui.exam_mode._COUNT_OPTIONS", ("1", "2", "3"))
    monkeypatch.setattr("ui.exam_mode._DURATION_OPTIONS", ("1", "30"))

    questions = [
        make_question(1),
        make_question(2),
        make_question(3, q_type="multiple", answer="AC"),
    ]
    app_state = _MockAppState()
    app_state._progress["exam_deck"] = [1, 2, 3]  # 预置牌堆 → 抽题顺序确定
    m = ExamMode(questions, app_state)
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
    """考试模式 Enter 无提交语义（交卷仅按钮触发，防误交卷）。

    协议实现方式：ExamMode 不定义 on_submit，主窗口经 getattr 鸭子路由
    自动跳过（定义空方法只为文档意图，属死代码）。
    """
    _start(mode, count="2", duration="30")

    # ExamMode 不实现 on_submit；主窗口 getattr 鸭子路由遇缺失自动跳过
    assert getattr(mode, "on_submit", None) is None

    assert len(mode.app_state.get_exam_history()) == 0
    assert mode.timer_running is True


def test_on_prev_next_route_in_exam_view(mode):
    """←/→ 快捷键鸭子转发到翻题。"""
    _start(mode)

    mode.on_next()
    assert mode.engine.get_current_index() == 1

    mode.on_prev()
    assert mode.engine.get_current_index() == 0


# ---------- H1 回归：交卷确认框与倒计时竞态 ----------


def test_submit_exam_confirmation_pauses_timer(mode, monkeypatch):
    """确认框（模态嵌套事件循环）期间停表：嵌套循环里 tick 到点不得先行
    自动交卷——否则用户点"是"后外层继续执行 → 历史重复入库 + 双报告。"""
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    _start(mode, count="1", duration="1")
    monkeypatch.setattr(mode.engine, "get_exam_elapsed_seconds", lambda: 3600)

    nested_ticks: list[int] = []

    def question_stub(*args, **kwargs):
        # 复现竞态触发条件：确认框打开期间若 timer 仍活跃，嵌套事件循环会
        # 派发超时 → _on_timer_tick → submit_exam(force=True) 先行交卷
        if mode._timer.isActive():
            mode._on_timer_tick()
            nested_ticks.append(1)
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", question_stub)

    mode.submit_exam()

    assert nested_ticks == []  # 修复后确认框期间 timer 已停
    assert len(mode.app_state.get_exam_history()) == 0
    # 取消交卷：考试仍在进行 → 恢复计时
    assert mode.timer_running is True
    assert mode._timer.isActive()

    # 测试卫生：本用例把引擎耗时 mock 成已过期（time_remaining=0），恢复的
    # 1s tick 会在后续用例的事件循环里触发真实自动交卷，打到已销毁的 panel
    # （shiboken RuntimeError）。生产场景下过期 tick 必在 1s 内触发，无此风险
    mode._timer.stop()


# ---------- M8 回归：考试计时跨模式页停/恢复 ----------


def test_hide_pauses_timer_and_show_resumes(mode):
    """切到其他模式页（hideEvent）停表；切回（showEvent）恢复并补刷新。

    注意：从未 show 过的 widget 调 hide() 不会派发 hideEvent，故先 show。
    """
    _start(mode, count="1", duration="30")
    mode.show()
    assert mode._timer.isActive()

    mode.hide()
    assert not mode._timer.isActive()
    assert mode.timer_running is True  # 语义保留：考试仍在进行，仅停 tick

    mode.show()
    assert mode._timer.isActive()
    assert mode.panel._time_text is not None


# ---------- 导航计数 ----------


def test_nav_count_reflects_answered(mode):
    """考试中 board-nav 计数 = 已答/总数；未开考为 None。"""
    assert mode.nav_count() is None

    _start(mode, count="3", duration="30")
    mode._select_option_by_letter("A")

    assert mode.nav_count() == "1/3"


# ---------- 考试报告对话框（P9-3 逐题回顾） ----------


def _report_with_two_wrong() -> dict:
    q1 = make_question(7, answer="A")
    q2 = make_question(8, q_type="multiple", answer="AC")
    return {
        "total_questions": 4,
        "correct": 2,
        "wrong": 2,
        "accuracy": 50.0,
        "time_used": "1分30秒",
        "wrong_questions": [q1, q2],
        "wrong_records": [
            {"question": q1, "selected": "B"},
            {"question": q2, "selected": "A"},
        ],
    }


def _option_cards(dlg) -> dict[str, object]:
    body = dlg._detail_scroll.widget()
    return {card.letter: card for card in body.findChildren(OptionRow)}


def test_report_dialog_walkthrough_states(qtbot):
    """报告错题逐题回顾：逐字母四象限判定 + 题型标签。"""
    from ui.exam_report_dialog import ExamReportDialog

    dlg = ExamReportDialog(None, _report_with_two_wrong())
    qtbot.addWidget(dlg)

    # 第一条错题（题7 单选，用户选 B，正确答案 A）
    cards = _option_cards(dlg)
    assert dlg._nav_pos.text() == "错题 1 / 2"
    assert cards["B"].property("state") == "selected"
    assert cards["B"].mark_label.text() == "已选 ✗"
    assert cards["A"].property("state") == "ok"
    assert cards["A"].mark_label.text() == "未选 ✓"
    assert cards["C"].property("state") == "wrong"
    assert dlg._prev_btn.isEnabled() is False
    assert dlg._next_btn.isEnabled() is True

    # 翻到第二条错题（题8 多选，正确答案 AC；用户只选了 A）
    dlg._go_next_wrong()
    cards = _option_cards(dlg)
    assert dlg._nav_pos.text() == "错题 2 / 2"
    assert cards["A"].property("state") == "selected"
    assert cards["A"].mark_label.text() == "已选 ✓"  # 选对：逐字母判定
    assert cards["C"].property("state") == "ok"  # 漏选的正确项
    assert cards["C"].mark_label.text() == "未选 ✓"
    assert cards["B"].property("state") == "wrong"
    assert cards["B"].mark_label.text() == "— 未选"
    assert dlg._next_btn.isEnabled() is False
    assert dlg._prev_btn.isEnabled() is True

    # 题型标签：题8 为多选题，meta 行 qType 变色
    body = dlg._detail_scroll.widget()
    multi_lbl = next(lbl for lbl in body.findChildren(QLabel) if lbl.text() == "多选题")
    assert multi_lbl.property("qType") == "multiple"


def test_report_dialog_all_correct_has_no_walkthrough(qtbot):
    """全对报告不出现回顾区。"""
    from ui.exam_report_dialog import ExamReportDialog

    report = _report_with_two_wrong()
    report["wrong_questions"] = []
    report["wrong_records"] = []
    dlg = ExamReportDialog(None, report)
    qtbot.addWidget(dlg)
    assert not hasattr(dlg, "_prev_btn")
    assert dlg.findChildren(OptionRow) == []
