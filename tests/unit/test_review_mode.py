"""review_mode.py 单元测试（P2-21）。

覆盖收藏切换、延迟保存、只看收藏筛选模式等子类行为。
"""
from unittest.mock import MagicMock

import pytest

from models import Question
from ui.review_mode import ReviewMode


def _make_question(number: int) -> Question:
    return Question(number=number, content=f"题 {number}", answer="A")


class _MockAppState:
    """最小 AppState 替代，避免真实 DataManager 与磁盘操作。"""

    def __init__(self, data_manager, progress):
        self._favorites: set[int] = set()
        self.save_safe = MagicMock(return_value=True)

    def toggle_favorite(self, q_num: int) -> bool:
        """返回 True 表示收藏，False 表示取消收藏。"""
        if q_num in self._favorites:
            self._favorites.remove(q_num)
            return False
        self._favorites.add(q_num)
        return True

    def is_favorite(self, q_num: int) -> bool:
        return q_num in self._favorites

    def get_favorites(self) -> list[int]:
        return sorted(self._favorites)


@pytest.fixture
def mode(root, monkeypatch):
    """提供一个已初始化的 ReviewMode 实例。"""
    # ReviewMode 继承 BaseMode，AppState 在 ui.base_mode 中解析
    monkeypatch.setattr('ui.base_mode.AppState', _MockAppState)
    questions = [_make_question(1), _make_question(2), _make_question(3)]
    mode = ReviewMode(root, questions, MagicMock(), {})
    mode.pack()
    yield mode
    mode.destroy()


def test_toggle_favorite_adds_and_saves_delayed(mode):
    """点击收藏应加入收藏列表并触发延迟保存。"""
    assert not mode.app_state.is_favorite(1)

    mode.toggle_favorite()

    assert mode.app_state.is_favorite(1)
    assert mode._pending_save is True
    assert mode._save_job_id is not None


def test_toggle_favorite_removes_and_refreshes_filter(mode):
    """筛选模式下取消收藏应将题目移出当前队列。"""
    # 先收藏题 1、2，再进入筛选模式
    mode.app_state.toggle_favorite(1)
    mode.app_state.toggle_favorite(2)
    mode.toggle_favorites_filter()

    assert mode.filtering_favorites is True
    assert mode.engine.queue_length() == 2

    # 当前第一题是 1，取消收藏后应只剩题 2
    mode.toggle_favorite()
    assert mode.app_state.is_favorite(1) is False
    assert mode.engine.queue_length() == 1
    assert mode.engine.get_current_question().number == 2


def test_filter_favorites_empty_exits_filter(mode, monkeypatch):
    """筛选模式下取消最后一道收藏，应自动退出筛选并恢复全量。"""
    monkeypatch.setattr('tkinter.messagebox.showinfo', lambda *a, **k: None)

    # 只收藏题 1 并进入筛选
    mode.app_state.toggle_favorite(1)
    mode.toggle_favorites_filter()
    assert mode.filtering_favorites is True

    # 取消唯一收藏
    mode.toggle_favorite()

    assert mode.filtering_favorites is False
    assert mode.engine.queue_length() == 3


def test_toggle_favorites_filter_no_favorites_shows_info(mode, monkeypatch):
    """没有收藏时进入筛选模式应提示用户且保持非筛选状态。"""
    info_calls = []
    monkeypatch.setattr('tkinter.messagebox.showinfo', lambda *a, **k: info_calls.append((a, k)))

    mode.toggle_favorites_filter()

    assert mode.filtering_favorites is False
    assert len(info_calls) == 1


def test_sync_favorite_button_text(mode):
    """收藏按钮文案应随收藏状态变化。"""
    assert mode.favorite_btn.cget('text') == '收藏'

    mode.app_state.toggle_favorite(1)
    mode._sync_favorite_button()

    assert '已收藏' in mode.favorite_btn.cget('text')


def test_filter_button_text(mode):
    """筛选按钮文案应随筛选状态变化。"""
    assert mode.filter_fav_btn.cget('text') == '只看收藏'

    mode.app_state.toggle_favorite(1)
    mode.app_state.toggle_favorite(2)
    mode.toggle_favorites_filter()

    assert mode.filter_fav_btn.cget('text') == '显示全部'
