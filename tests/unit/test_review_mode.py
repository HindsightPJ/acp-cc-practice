"""review_mode.py 单元测试（PySide6 版）。

覆盖：收藏（P6 补回的收藏按钮）、只看收藏筛选、筛选中取消收藏出队、
Enter 显示/隐藏答案、自动显示答案、跳转输入、主窗口协议。
"""

from unittest.mock import MagicMock

import pytest

from app_state import AppState
from models import Option, Question
from ui.review_mode import ReviewMode

pytestmark = pytest.mark.gui


def _make_question(number: int) -> Question:
    return Question(
        number=number,
        content=f"题 {number}",
        options=[Option("A", "选项 A"), Option("B", "选项 B")],
        answer="A",
        explanation=f"解析 {number}",
    )


class _MockAppState(AppState):
    """真实 AppState + mock 落盘。"""

    def __init__(self) -> None:
        super().__init__(MagicMock(), progress={})
        self.save_safe = MagicMock(return_value=True)


@pytest.fixture
def mode(qtbot):
    m = ReviewMode([_make_question(1), _make_question(2), _make_question(3)], _MockAppState())
    qtbot.addWidget(m)
    return m


# ---------- 收藏（P6 补回按钮后的回归） ----------


def test_toggle_favorite_adds_and_saves_delayed(mode):
    """点击收藏加入收藏列表并触发防抖保存。"""
    assert not mode.app_state.is_favorite(1)

    mode.toggle_favorite()

    assert mode.app_state.is_favorite(1) is True
    assert mode._pending_save is True


def test_favorite_button_text_syncs(mode):
    """收藏按钮文案随收藏状态变化。"""
    assert mode.favorite_btn.text() == "收藏"

    mode.toggle_favorite()

    assert "已收藏" in mode.favorite_btn.text()

    mode.toggle_favorite()

    assert mode.favorite_btn.text() == "收藏"


def test_toggle_favorite_without_data_manager(qtbot):
    """data_manager 为 None 时收藏切换仍生效。"""
    m = ReviewMode([_make_question(1)], _MockAppState())
    qtbot.addWidget(m)

    m.toggle_favorite()

    assert m.app_state.is_favorite(1) is True


# ---------- 只看收藏筛选 ----------


def test_toggle_favorites_filter_builds_queue(mode):
    """开启筛选后引擎队列 = 收藏题列表。"""
    mode.app_state.toggle_favorite(1)
    mode.app_state.toggle_favorite(2)

    mode.toggle_favorites_filter(True)

    assert mode.favorites_only is True
    assert mode.engine.queue_length() == 2
    assert mode.engine.get_question_at(0).number == 1
    assert mode.engine.get_question_at(1).number == 2


def test_filter_favorites_empty_keeps_empty_state(mode):
    """无收藏时开启筛选 → 空态展示（0/0），保持筛选状态。"""
    mode.toggle_favorites_filter(True)

    assert mode.favorites_only is True
    assert mode.engine.queue_length() == 0
    assert mode.nav_count() == "0/0"
    assert "暂无收藏" in mode.detail_card.stem.text()


def test_unfavorite_in_filter_mode_removes_from_queue(mode):
    """筛选模式下取消收藏：题目移出队列，加载剩余收藏。"""
    mode.app_state.toggle_favorite(1)
    mode.app_state.toggle_favorite(2)
    mode.toggle_favorites_filter(True)

    mode.toggle_favorite()  # 取消收藏当前题（题 1）

    assert mode.app_state.is_favorite(1) is False
    assert mode.engine.queue_length() == 1
    assert mode.engine.get_current_question().number == 2


def test_close_filter_restores_full_queue(mode):
    """关闭筛选恢复全量队列。"""
    mode.app_state.toggle_favorite(1)
    mode.toggle_favorites_filter(True)

    mode.toggle_favorites_filter(False)

    assert mode.favorites_only is False
    assert mode.engine.queue_length() == 3


# ---------- 答案显示 ----------


def test_on_submit_toggles_answer(mode):
    """Enter 显示答案（verdict + 解析）→ 再按隐藏。"""
    mode.on_submit()

    assert mode.detail_card._exp_box.isVisibleTo(mode.detail_card)
    assert "正确答案" in mode.detail_card.exp_result.text()

    mode.on_submit()

    assert mode.detail_card.exp_result.property("verdict") is None


def test_auto_show_answer_toggle(mode, qtbot):
    """开启自动显示后加载题目即自动渲染答案。"""
    mode.auto_check.setChecked(True)

    qtbot.waitUntil(
        lambda: mode.detail_card.exp_result.property("verdict") is not None, timeout=2000
    )


def test_auto_show_skipped_when_switch_off(mode):
    """开关关闭时不自动渲染答案。"""
    mode.load_question()

    assert mode.detail_card.exp_result.property("verdict") is None


# ---------- 跳转 / 导航 ----------


def test_jump_from_input(mode):
    """跳转输入 1-based 题号 → 队列索引。"""
    mode.jump_edit.setText("3")
    mode._jump_from_input()

    assert mode.engine.get_current_index() == 2
    assert mode.jump_edit.text() == ""


def test_jump_from_input_invalid_is_noop(mode):
    """非数字输入清空且不跳转。"""
    mode.jump_edit.setText("abc")
    mode._jump_from_input()

    assert mode.engine.get_current_index() == 0
    assert mode.jump_edit.text() == ""


def test_jump_from_input_rejects_unicode_digit(mode):
    """M10: 上标数字（"²"）isdigit() 为 True 但 int() 抛 ValueError。

    修复前异常穿透 returnPressed 信号槽（PySide6 只打印 traceback，
    用户操作无响应反馈）；限定 ASCII 数字后非法输入清空、不跳转。
    """
    mode.jump_edit.setText("²")
    mode._jump_from_input()

    assert mode.engine.get_current_index() == 0
    assert mode.jump_edit.text() == ""


def test_next_prev_nav(mode):
    """→/← 翻题与边界。"""
    mode.on_next()
    assert mode.engine.get_current_index() == 1

    mode.on_prev()
    assert mode.engine.get_current_index() == 0

    mode.on_prev()  # 已在第一题，无操作
    assert mode.engine.get_current_index() == 0


def test_next_at_boundary_does_not_crash(mode):
    """末题点下一题不崩溃（信息提示被静音）。"""
    mode.engine.set_current_index(2)

    mode.on_next()

    assert mode.engine.get_current_index() == 2


# ---------- 主窗口协议 ----------


def test_nav_count_and_modeline(mode):
    """nav_count = 位置/总数；modeline 含 REVIEW 段与收藏数。"""
    assert mode.nav_count() == "1/3"
    assert "REVIEW" in mode.modeline_text()
    assert "收藏 0" in mode.modeline_text()


def test_state_changed_emitted_on_nav(mode, qtbot):
    """翻题后发出 state_changed（主窗口刷新信号）。"""
    received = []
    mode.state_changed.connect(lambda: received.append(1))

    mode.on_next()

    assert received == [1]
