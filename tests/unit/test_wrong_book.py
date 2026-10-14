"""wrong_book.py 单元测试（PySide6 版）。

覆盖：UI 层禁止直访 QuizEngine 内部状态（TD-15 静态扫描）、
错题练习完成流程（P6 修复 on_finish 不可达后的回归）、
>=80% 正确率只移除答对的错题（P1-4）。
"""

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QMessageBox

from app_state import AppState
from models import Option, Question
from ui.wrong_book import WrongBookPage

pytestmark = pytest.mark.gui


def _make_question(number: int, answer: str = "A") -> Question:
    return Question(
        number=number,
        content=f"错题 {number}",
        options=[Option("A", "选项 A"), Option("B", "选项 B")],
        answer=answer,
    )


@pytest.fixture
def state():
    s = AppState(MagicMock(), progress={})
    s.set_wrong_questions([1, 2])
    return s


@pytest.fixture
def page(qtbot, state):
    p = WrongBookPage([_make_question(1), _make_question(2)], state)
    qtbot.addWidget(p)
    return p


# ---------- 静态扫描（TD-15） ----------


def test_ui_source_no_direct_engine_internal_state_access():
    """ui 目录下任何模块都不应直接访问 QuizEngine 内部状态属性。"""
    from pathlib import Path

    ui_dir = Path(__file__).parent.parent.parent / "ui"
    forbidden = (
        "engine.current_index",
        "engine.questions_queue",
        "engine.answers_record",
        "engine.stats",
        "engine.exam_start_time",
        "engine.all_questions",
        "practice_engine.current_index",
        "practice_engine.questions_queue",
        "practice_engine.answers_record",
        "practice_engine.stats",
        "practice_engine.exam_start_time",
        "practice_engine.all_questions",
    )
    for src_file in ui_dir.glob("*.py"):
        content = src_file.read_text(encoding="utf-8")
        for attr in forbidden:
            assert attr not in content, f"{src_file.name} directly accesses {attr}"


# ---------- 列表视图 ----------


def test_list_view_populates_from_state(page, state):
    """列表视图按错题快照渲染行数与计数标题。"""
    assert page.table.rowCount() == 2
    assert "2 题" in page.count_label.text()

    state.set_wrong_questions([])
    page._refresh_table()

    assert page.table.rowCount() == 0
    assert "0 题" in page.count_label.text()


def test_start_practice_empty_book_shows_info(page, state):
    """错题本为空时开始练习仅提示，不切入练习视图。"""
    state.set_wrong_questions([])

    page.start_practice()

    assert page.panel is None
    assert page.stack.currentIndex() == 0


# ---------- 练习完成流程（P6 修复 on_finish 不可达后的回归） ----------


def test_practice_finished_removes_only_correct(page, state, monkeypatch):
    """P1-4: 完成后只移除本次答对的错题，答错保留。"""
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    page.start_practice()

    # 题 1 答对（A），题 2 答错（B）
    page.panel.handle_option_click("A")
    page.panel.submit_answer()
    page.panel.next_question()
    page.panel.handle_option_click("B")
    page.panel.submit_answer()

    # 末题已答后再点下一题 → 触发完成流程（P6 修复路径）
    page.panel.next_question()

    assert state.get_wrong_questions() == [2]
    assert state._data_manager.save_progress.call_count >= 1  # 经 AppState 落盘
    assert page.stack.currentIndex() == 0  # 回列表视图
    assert page.panel is None


def test_practice_finished_declined_keeps_wrong_book(page, state, monkeypatch):
    """完成时选择不移除 → 错题本原样保留。"""
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    page.start_practice()

    page.panel.handle_option_click("A")
    page.panel.submit_answer()
    page.panel.next_question()
    page.panel.handle_option_click("B")
    page.panel.submit_answer()
    page.panel.next_question()

    assert sorted(state.get_wrong_questions()) == [1, 2]


def test_unanswered_final_next_shows_hint_only(page):
    """末题未作答点下一题只提示，不触发完成流程。"""
    page.start_practice()

    page.panel.next_question()

    assert page.panel is not None  # 仍在练习视图


# ---------- 主窗口协议 ----------


def test_nav_count_tracks_wrong_book_size(page, state):
    """board-nav 错题行计数 = 错题本数量。"""
    assert page.nav_count() == "2"

    state.set_wrong_questions([])
    assert page.nav_count() == "0"


def test_modeline_switches_with_view(page):
    """modeline 随列表/练习视图切换。"""
    assert "错题 2 题" in page.modeline_text()

    page.start_practice()

    assert "错题练习" in page.modeline_text()


def test_letter_keys_only_active_in_practice_view(page):
    """列表视图按键无语义；练习视图路由到选项点击。"""
    page.on_letter("A")  # 列表视图：无操作
    assert page.practice_session is None

    page.start_practice()
    page.on_letter("A")
    assert page.practice_session.selected_answers == ["A"]


def test_on_submit_delegates_in_practice_view(page):
    """练习视图 Enter 委托 panel 提交。"""
    page.start_practice()
    page.on_letter("A")

    page.on_submit()

    assert page.practice_session.is_answered is True
