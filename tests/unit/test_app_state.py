"""app_state.py 单元测试。

聚焦 save_safe 的新行为（P0-4: 不再静默吞错）：
  - 成功时返回 True
  - 失败时返回 False，不抛异常，记录 warning 日志

P1-1: count 方法返回值与 len(get_xxx()) 一致，但 O(1) 读取。
"""

from unittest.mock import MagicMock

import pytest

from app_state import AppState
from data_manager import DataSaveError


@pytest.fixture
def app_state():
    """构建带 mock data_manager 的 AppState。"""
    data_manager = MagicMock()
    return AppState(data_manager, progress={})


def test_save_safe_success_returns_true(app_state):
    """save 成功时 save_safe 返回 True。"""
    app_state._data_manager.save_progress = MagicMock()
    assert app_state.save_safe() is True
    app_state._data_manager.save_progress.assert_called_once()


def test_save_safe_oserror_returns_false(app_state):
    """save 抛 OSError 时 save_safe 返回 False，不抛异常。"""
    app_state._data_manager.save_progress = MagicMock(side_effect=OSError("disk full"))
    assert app_state.save_safe() is False


def test_save_safe_datasaveerror_returns_false(app_state):
    """save 抛 DataSaveError 时 save_safe 返回 False，不抛异常。"""
    app_state._data_manager.save_progress = MagicMock(side_effect=DataSaveError("write failed"))
    assert app_state.save_safe() is False


def test_save_safe_valueerror_returns_false(app_state):
    """save 抛 ValueError 时 save_safe 返回 False，不抛异常。"""
    app_state._data_manager.save_progress = MagicMock(side_effect=ValueError("bad data"))
    assert app_state.save_safe() is False


def test_save_safe_logs_warning_on_failure(app_state, caplog):
    """save 失败时记录 warning 日志（P0-4: 不再静默吞错）。"""
    app_state._data_manager.save_progress = MagicMock(side_effect=OSError("disk full"))
    with caplog.at_level("WARNING", logger="app_state"):
        app_state.save_safe()
    assert any("保存学习进度失败" in record.message for record in caplog.records)


# ---------- P1-1: count 方法测试 ----------


def test_wrong_count_empty(app_state):
    """空错题本时 wrong_count 返回 0。"""
    assert app_state.wrong_count() == 0


def test_wrong_count_after_add(app_state):
    """添加错题后 wrong_count 反映数量。"""
    app_state.add_wrong_question(1)
    app_state.add_wrong_question(2)
    app_state.add_wrong_question(3)
    assert app_state.wrong_count() == 3


def test_wrong_count_dedup(app_state):
    """重复添加同一题号不重复计数。"""
    app_state.add_wrong_question(1)
    app_state.add_wrong_question(1)
    assert app_state.wrong_count() == 1


# ---------- 考试卡组（draw_exam_questions） ----------


def test_draw_exam_deck_first_draw_consumes_head(app_state):
    """预置牌堆时按顺序从头部抽取，余牌保留。"""
    app_state._progress["exam_deck"] = [5, 3, 8, 1, 9]
    drawn = app_state.draw_exam_questions(2, [1, 3, 5, 8, 9])
    assert drawn == [5, 3]
    assert app_state._progress["exam_deck"] == [8, 1, 9]


def test_draw_exam_deck_covers_all_within_cycle(app_state, monkeypatch):
    """连续抽题一个周期后全库每题至少出现一次（卡组核心保证）。"""
    bank = list(range(1, 21))  # 20 题
    seen: set[int] = set()
    for _ in range(8):  # 每次抽 3，8 次远超一个周期
        seen.update(app_state.draw_exam_questions(3, bank))
    assert seen == set(bank)


def test_draw_exam_deck_no_dup_within_single_draw(app_state):
    """单次抽题（含周期边界重洗）内不出现重复题号。"""
    bank = list(range(1, 11))
    for _ in range(30):  # 多轮抽牌，覆盖多次周期边界
        drawn = app_state.draw_exam_questions(4, bank)
        assert len(drawn) == 4
        assert len(set(drawn)) == 4


def test_draw_exam_deck_resets_on_bank_change(app_state):
    """题库升级/降级（旧牌堆题号不在新库）→ 整库重洗，不抽到已删题。"""
    app_state._progress["exam_deck"] = [1, 2, 99]  # 99 已从新库删除
    drawn = app_state.draw_exam_questions(2, [1, 2, 3])
    assert set(drawn) <= {1, 2, 3}


def test_draw_exam_deck_count_clamped_to_bank(app_state):
    """抽题数超过全库时钳位为全库题数。"""
    drawn = app_state.draw_exam_questions(50, [1, 2, 3])
    assert len(drawn) == 3


def test_draw_exam_deck_empty_bank_returns_empty(app_state):
    """空题库返回空列表不抛异常。"""
    assert app_state.draw_exam_questions(5, []) == []


def test_draw_exam_deck_seeded_order_without_prefill(app_state, monkeypatch):
    """无预置牌堆时自动整库洗牌建堆：抽满一个周期仍是全库覆盖。"""
    fixed_order = [3, 1, 2]

    class _Seq:
        def __init__(self) -> None:
            self.calls = 0

        def __call__(self, items: list[int]) -> None:
            items[:] = fixed_order.copy()
            self.calls += 1

    monkeypatch.setattr("app_state.random.shuffle", _Seq())
    bank = [1, 2, 3]
    assert app_state.draw_exam_questions(3, bank) == [3, 1, 2]


def test_wrong_count_after_remove(app_state):
    """移除错题后 wrong_count 反映数量。"""
    app_state.add_wrong_question(1)
    app_state.add_wrong_question(2)
    app_state.remove_wrong_question(1)
    assert app_state.wrong_count() == 1


def test_wrong_count_matches_len_get_wrong_questions(app_state):
    """wrong_count() 与 len(get_wrong_questions()) 结果一致。"""
    app_state.add_wrong_question(10)
    app_state.add_wrong_question(20)
    assert app_state.wrong_count() == len(app_state.get_wrong_questions())


def test_favorites_count_empty(app_state):
    """空收藏时 favorites_count 返回 0。"""
    assert app_state.favorites_count() == 0


def test_favorites_count_after_toggle(app_state):
    """切换收藏后 favorites_count 反映数量。"""
    app_state.toggle_favorite(1)
    app_state.toggle_favorite(2)
    assert app_state.favorites_count() == 2
    app_state.toggle_favorite(1)  # 取消
    assert app_state.favorites_count() == 1


def test_exam_history_count_empty(app_state):
    """空考试历史时 exam_history_count 返回 0。"""
    assert app_state.exam_history_count() == 0


def test_exam_history_count_after_add(app_state):
    """添加考试历史后 exam_history_count 反映数量。"""
    app_state.add_exam_history({"date": "2026-01-01", "correct": 80})
    app_state.add_exam_history({"date": "2026-01-02", "correct": 90})
    assert app_state.exam_history_count() == 2


def test_exam_history_count_capped_at_20(app_state):
    """考试历史超过 20 条时 exam_history_count 反映截断后的数量。"""
    for i in range(25):
        app_state.add_exam_history({"date": f"2026-01-{i:02d}", "correct": i})
    assert app_state.exam_history_count() == 20
