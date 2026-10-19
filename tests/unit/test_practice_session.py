"""practice_session.py 单元测试。

P2-1: 重点验证重复提交不会导致 practice_stats 双倍计数。
覆盖范围：
- 首次提交更新统计
- 重复提交（切走再切回）不重复计数
- 答错加入错题
- reset_session 后重新计数
- 单选/多选选项处理
"""

from unittest.mock import MagicMock

import pytest

from app_state import AppState
from models import Question, Option
from quiz_engine import QuizEngine
from ui.practice_session import PracticeSession


# ---------- 辅助函数 ----------


def make_single_question(number: int, answer: str = "A") -> Question:
    """构造单选题。"""
    return Question(
        number=number,
        content=f"单选题 {number} 内容",
        options=[
            Option("A", "选项 A"),
            Option("B", "选项 B"),
            Option("C", "选项 C"),
            Option("D", "选项 D"),
        ],
        answer=answer,
        type="single",
        explanation=f"解析 {number}",
    )


def make_multi_question(number: int, answer: str = "ABC") -> Question:
    """构造多选题。"""
    return Question(
        number=number,
        content=f"多选题 {number} 内容",
        options=[
            Option("A", "选项 A"),
            Option("B", "选项 B"),
            Option("C", "选项 C"),
            Option("D", "选项 D"),
        ],
        answer=answer,
        type="multiple",
        explanation=f"解析 {number}",
    )


# ---------- fixtures ----------


@pytest.fixture
def questions():
    return [
        make_single_question(1, answer="A"),
        make_single_question(2, answer="B"),
        make_multi_question(3, answer="ABC"),
    ]


@pytest.fixture
def app_state():
    """构建带 mock data_manager 的 AppState。"""
    data_manager = MagicMock()
    return AppState(data_manager, progress={})


@pytest.fixture
def session(questions, app_state):
    """构建 PracticeSession 实例。"""
    engine = QuizEngine(questions)
    engine.start_practice_mode(shuffle=False)
    s = PracticeSession(engine, app_state)
    s.reset_session(shuffle=False)
    return s


# ---------- 首次提交 ----------


def test_first_submission_increments_stats(session, app_state):
    """首次提交答案应更新练习统计。"""
    session.get_question_type(session.engine.get_current_question())
    session.handle_option_click("A", 4)
    result = session.submit_answer()

    assert result is not None
    assert session.is_answered is True
    stats = app_state.get_practice_stats()
    assert stats["total"] == 1
    assert stats["correct"] == 1


# ---------- M11: 选项切换语义与考试对齐（ui/selection.toggle_letter） ----------


def test_single_choice_reclick_deselects(session):
    """单选重复点击同一字母 = 取消。

    M11 修复前练习侧为保持选中（用户无法取消选择），与考试侧语义漂移；
    两侧现共用 ui/selection.toggle_letter，语义单一来源。
    """
    session.get_question_type(session.engine.get_current_question())  # 题1 = single
    session.handle_option_click("A", 4)
    assert session.selected_answers == ["A"]

    session.handle_option_click("A", 4)
    assert session.selected_answers == []


def test_single_choice_switch_replaces(session):
    """单选点其他字母 = 改选（非累加）。"""
    session.get_question_type(session.engine.get_current_question())
    session.handle_option_click("A", 4)
    session.handle_option_click("B", 4)
    assert session.selected_answers == ["B"]


def test_multi_choice_toggle_matches_exam_semantics(session):
    """多选对称差切换：A→AC→C（与 ExamSession 语义一致）。"""
    session.get_question_type(session.engine.get_current_question())  # 题1 single
    session.engine.set_current_index(2)  # 题3 = multiple
    session.get_question_type(session.engine.get_current_question())

    session.handle_option_click("A", 4)
    session.handle_option_click("C", 4)
    assert session.selected_answers == ["A", "C"]

    session.handle_option_click("A", 4)
    assert session.selected_answers == ["C"]


def test_first_wrong_submission_adds_wrong_question(session, app_state):
    """首次提交答错应加入错题本。"""
    session.get_question_type(session.engine.get_current_question())
    session.handle_option_click("B", 4)  # 答错（正确答案是 A）
    session.submit_answer()

    assert app_state.is_wrong_question(1) is True


# ---------- P2-1: 重复提交不重复计数 ----------


def test_resubmit_after_navigate_back_does_not_double_count(session, app_state):
    """P2-1: 切走再切回重新提交，不应重复计数。

    场景：
    1. 答 题 1（正确）→ stats.total = 1
    2. 切到题 2，再切回题 1
    3. 重新选择并提交 → stats.total 仍应为 1（不重复计数）
    """
    # 1. 题 1 答对
    session.get_question_type(session.engine.get_current_question())
    session.handle_option_click("A", 4)
    session.submit_answer()
    assert app_state.get_practice_stats()["total"] == 1

    # 2. 切到题 2
    session.next_question()
    session.reset_selection()  # 模拟 load_current_question 的调用
    # 3. 切回题 1
    session.prev_question()
    session.reset_selection()  # 模拟 load_current_question 的调用

    # 4. 重新答题并提交
    session.get_question_type(session.engine.get_current_question())
    session.handle_option_click("A", 4)
    result = session.submit_answer()

    assert result is not None
    # P2-1: 重复提交不应导致双倍计数
    assert app_state.get_practice_stats()["total"] == 1


def test_resubmit_wrong_answer_does_not_double_count_wrong(session, app_state):
    """P2-1: 重复提交答错不重复加入错题本。"""
    # 题 1 答错
    session.get_question_type(session.engine.get_current_question())
    session.handle_option_click("B", 4)
    session.submit_answer()
    assert app_state.wrong_count() == 1

    # 切走再切回
    session.next_question()
    session.reset_selection()
    session.prev_question()
    session.reset_selection()

    # 重新答错
    session.get_question_type(session.engine.get_current_question())
    session.handle_option_click("C", 4)
    session.submit_answer()

    # 错题本仍只有 1 题（去重）
    assert app_state.wrong_count() == 1
    # 统计不重复计数
    assert app_state.get_practice_stats()["wrong"] == 1


def test_resubmit_correct_after_wrong_keeps_wrong_stats(session, app_state):
    """P2-1: 首次答错后重新答对，统计仍记录首次结果（不重复计数）。"""
    # 题 1 答错
    session.get_question_type(session.engine.get_current_question())
    session.handle_option_click("B", 4)
    session.submit_answer()
    assert app_state.get_practice_stats()["wrong"] == 1

    # 切走再切回
    session.next_question()
    session.reset_selection()
    session.prev_question()
    session.reset_selection()

    # 重新答对
    session.get_question_type(session.engine.get_current_question())
    session.handle_option_click("A", 4)
    session.submit_answer()

    # P2-1: 统计仍记录首次结果（1 错），不因重新答对而改变
    stats = app_state.get_practice_stats()
    assert stats["total"] == 1
    assert stats["wrong"] == 1
    assert stats["correct"] == 0


# ---------- reset_session ----------


def test_reset_session_clears_answered_state(questions, app_state):
    """reset_session 后所有题重新变为首次提交。"""
    engine = QuizEngine(questions)
    engine.start_practice_mode(shuffle=False)
    session = PracticeSession(engine, app_state)
    session.reset_session(shuffle=False)

    # 题 1 答对
    session.get_question_type(session.engine.get_current_question())
    session.handle_option_click("A", 4)
    session.submit_answer()
    assert app_state.get_practice_stats()["total"] == 1

    # 重新开始
    session.reset_session(shuffle=False)

    # 题 1 重新答对
    session.get_question_type(session.engine.get_current_question())
    session.handle_option_click("A", 4)
    session.submit_answer()

    # reset_session 后应再次计数
    assert app_state.get_practice_stats()["total"] == 2


# ---------- 选项处理 ----------


def test_single_choice_option_select(session):
    """单选题点击选项应替换选中。"""
    session.get_question_type(session.engine.get_current_question())
    session.handle_option_click("A", 4)
    assert session.selected_answers == ["A"]

    session.handle_option_click("B", 4)
    assert session.selected_answers == ["B"]


def test_multi_choice_option_toggle(session):
    """多选题点击选项应切换选中。"""
    # 切到题 3（多选题）
    session.next_question()
    session.next_question()
    session.reset_selection()
    question = session.engine.get_current_question()
    session.get_question_type(question)

    session.handle_option_click("A", 4)
    session.handle_option_click("B", 4)
    assert session.selected_answers == ["A", "B"]

    # 再次点击 B 应取消
    session.handle_option_click("B", 4)
    assert session.selected_answers == ["A"]


def test_handle_option_click_after_answered_is_noop(session):
    """已答题后点击选项应无效。"""
    session.get_question_type(session.engine.get_current_question())
    session.handle_option_click("A", 4)
    session.submit_answer()

    # 已答题后再点击
    session.handle_option_click("B", 4)
    assert session.selected_answers == ["A"]


def test_submit_without_selection_returns_none(session):
    """未选择答案时提交返回 None。"""
    result = session.submit_answer()
    assert result is None


# ---------- 会话快照（进度恢复） ----------


def test_export_restore_roundtrip(questions, app_state):
    """快照导出→恢复后，队列/索引/答案/统计应完整还原。"""
    engine = QuizEngine(questions)
    engine.start_practice_mode(shuffle=False)
    session = PracticeSession(engine, app_state)
    session.reset_session(shuffle=False)

    # 题 1 答对，切到题 2
    session.get_question_type(session.engine.get_current_question())
    session.handle_option_click("A", 4)
    session.submit_answer()
    session.next_question()

    state = session.export_state()
    assert state["queue"] == [1, 2, 3]
    assert state["index"] == 1
    assert state["answers"] == {"0": "A"}

    # 模拟应用重启：全新 session 从快照恢复
    new_engine = QuizEngine(questions)
    new_engine.start_practice_mode(shuffle=False)
    new_session = PracticeSession(new_engine, app_state)
    assert new_session.restore_state(state) is True

    assert new_session.engine.get_current_index() == 1
    assert new_session.engine.get_current_question().number == 2
    # 答案按 record_exam_answer 重新写入，统计从 answers_record 重算
    assert new_session.engine.is_answered(0) is True
    assert new_session.engine.get_stats() == {"correct": 1, "wrong": 0, "total": 1}

    # 恢复后重新提交题 1：不重复计数（"已答"事实随快照保留）
    new_session.engine.set_current_index(0)
    new_session.get_question_type(new_session.engine.get_current_question())
    new_session.handle_option_click("A", 4)
    new_session.submit_answer()
    assert app_state.get_practice_stats()["total"] == 1


def test_export_clamps_index_after_finish(questions, app_state):
    """队列完成时（index 越界触发 on_finish），快照索引应钳到末题。"""
    engine = QuizEngine(questions)
    engine.start_practice_mode(shuffle=False)
    session = PracticeSession(engine, app_state)
    session.reset_session(shuffle=False)

    # 连续 next 越过末题（模拟完成后）
    session.engine.set_current_index(len(questions))  # 越界

    state = session.export_state()
    assert state["index"] == len(questions) - 1

    new_engine = QuizEngine(questions)
    new_engine.start_practice_mode(shuffle=False)
    assert PracticeSession(new_engine, app_state).restore_state(state) is True


def test_restore_rejects_when_question_bank_changed(questions, app_state):
    """题库变化（快照题号缺失）时应整体放弃恢复。"""
    engine = QuizEngine(questions)
    engine.start_practice_mode(shuffle=False)
    session = PracticeSession(engine, app_state)
    session.reset_session(shuffle=False)

    state = session.export_state()
    state["queue"] = [1, 2, 999]  # 999 不在题库

    new_engine = QuizEngine(questions)
    new_engine.start_practice_mode(shuffle=False)
    new_session = PracticeSession(new_engine, app_state)
    assert new_session.restore_state(state) is False
    # 拒绝恢复不应部分修改 engine 状态
    assert new_session.engine.queue_length() == len(questions)
    assert new_session.engine.get_current_index() == 0


def test_restore_rejects_corrupt_snapshot(questions, app_state):
    """结构损坏/越界的快照应返回 False 且不修改 engine 状态。"""
    engine = QuizEngine(questions)
    engine.start_practice_mode(shuffle=False)
    session = PracticeSession(engine, app_state)
    session.reset_session(shuffle=False)

    bad_states = [
        {},
        {"queue": []},
        {"queue": [1, 2, 3], "index": "x", "answers": {}},
        {"queue": [1, 2, 3], "index": 99, "answers": {}},
        {"queue": [1, 2, 3], "index": 0, "answers": "not-a-dict"},
        {"queue": "1,2,3", "index": 0, "answers": {}},
        {"queue": [1, 2, 3], "index": -1, "answers": {}},
    ]
    for bad in bad_states:
        assert session.restore_state(bad) is False, f"应拒绝: {bad}"
        # 失败路径不得产生部分修改
        assert session.engine.queue_length() == len(questions)
        assert session.engine.get_current_index() == 0


def test_shuffle_flag_roundtrip(questions, app_state):
    """shuffle 状态应随快照导出并在恢复时还原。"""
    engine = QuizEngine(questions)
    engine.start_practice_mode(shuffle=False)
    session = PracticeSession(engine, app_state)
    session.reset_session(shuffle=True)

    state = session.export_state()
    assert state["shuffle"] is True

    new_engine = QuizEngine(questions)
    new_engine.start_practice_mode(shuffle=False)
    new_session = PracticeSession(new_engine, app_state)
    assert new_session.restore_state(state) is True
    assert new_session._shuffle is True
