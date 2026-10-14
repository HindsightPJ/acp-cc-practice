"""应用状态对象（TD-30）：解耦 UI 与持久化状态管理。

UI 层通过 AppState 读写学习进度，不再直接调用 data_manager.save_progress，
也不再直接访问原始 progress dict。
"""

import logging
from typing import Any

from data_manager import DataManager, DataSaveError, default_progress

logger = logging.getLogger(__name__)


class AppState:
    """封装学习进度及其持久化操作。

    提供类型安全的方法访问错题、收藏、练习统计、考试历史等数据，
    所有修改最终通过 data_manager.save_progress 落盘。
    """

    def __init__(self, data_manager: DataManager, progress: dict[str, Any] | None = None) -> None:
        self._data_manager = data_manager
        self._progress: dict[str, Any] = progress if progress is not None else {}
        self._ensure_defaults()

    def _ensure_defaults(self) -> None:
        """确保进度字典包含所有必需字段（默认结构单一来源：default_progress）。"""
        for key, value in default_progress().items():
            self._progress.setdefault(key, value)

    # ---------- 练习统计 ----------
    def get_practice_stats(self) -> dict[str, int]:
        return dict(self._progress.get("practice_stats", {"correct": 0, "wrong": 0, "total": 0}))

    def increment_practice_stats(self, is_correct: bool) -> None:
        stats = self._progress.setdefault("practice_stats", {"correct": 0, "wrong": 0, "total": 0})
        stats["total"] = stats.get("total", 0) + 1
        if is_correct:
            stats["correct"] = stats.get("correct", 0) + 1
        else:
            stats["wrong"] = stats.get("wrong", 0) + 1

    # ---------- 错题 ----------
    def get_wrong_questions(self) -> list[int]:
        return list(self._progress.get("wrong_questions", []))

    def wrong_count(self) -> int:
        """返回错题数量（P1-1: O(1) 读取，避免仅为取长度而 O(N) 浅拷贝）。"""
        return len(self._progress.get("wrong_questions", []))

    def add_wrong_question(self, q_num: int) -> None:
        wrong = self._progress.setdefault("wrong_questions", [])
        if q_num not in wrong:
            wrong.append(q_num)

    def remove_wrong_question(self, q_num: int) -> None:
        wrong = self._progress.get("wrong_questions", [])
        if q_num in wrong:
            wrong.remove(q_num)

    def set_wrong_questions(self, q_nums: list[int]) -> None:
        self._progress["wrong_questions"] = list(q_nums)

    def is_wrong_question(self, q_num: int) -> bool:
        return q_num in self._progress.get("wrong_questions", [])

    # ---------- 收藏 ----------
    def get_favorites(self) -> list[int]:
        return list(self._progress.get("favorites", []))

    def favorites_count(self) -> int:
        """返回收藏数量（P1-1: O(1) 读取，避免仅为取长度而 O(N) 浅拷贝）。"""
        return len(self._progress.get("favorites", []))

    def add_favorite(self, q_num: int) -> None:
        favorites = self._progress.setdefault("favorites", [])
        if q_num not in favorites:
            favorites.append(q_num)

    def remove_favorite(self, q_num: int) -> None:
        favorites = self._progress.get("favorites", [])
        if q_num in favorites:
            favorites.remove(q_num)

    def toggle_favorite(self, q_num: int) -> bool:
        """切换收藏状态，返回切换后是否已收藏。"""
        favorites = self._progress.setdefault("favorites", [])
        if q_num in favorites:
            favorites.remove(q_num)
            return False
        favorites.append(q_num)
        return True

    def is_favorite(self, q_num: int) -> bool:
        return q_num in self._progress.get("favorites", [])

    # ---------- 考试历史 ----------
    def get_exam_history(self) -> list[dict[str, Any]]:
        return list(self._progress.get("exam_history", []))

    def exam_history_count(self) -> int:
        """返回考试历史记录数（P1-1: O(1) 读取，避免仅为取长度而 O(N) 浅拷贝）。"""
        return len(self._progress.get("exam_history", []))

    def add_exam_history(self, entry: dict[str, Any]) -> None:
        history = self._progress.setdefault("exam_history", [])
        history.append(entry)
        # 仅保留最近 20 条，避免进度文件无限增长
        self._progress["exam_history"] = history[-20:]

    # ---------- 练习会话快照（进度恢复） ----------
    def get_practice_progress(self) -> dict[str, Any]:
        """返回练习会话快照（无/格式异常时返回空 dict）。"""
        data = self._progress.get("practice_progress")
        return dict(data) if isinstance(data, dict) else {}

    def set_practice_progress(self, data: dict[str, Any]) -> None:
        """写入练习会话快照（随下次 save_safe 一并落盘）。"""
        self._progress["practice_progress"] = data

    # ---------- 持久化 ----------
    def save(self) -> None:
        """立即保存进度到 data_manager。"""
        self._data_manager.save_progress(self._progress)

    def save_safe(self) -> bool:
        """保存进度并捕获保存错误，返回是否成功。

        P0-4: 不再静默吞错——失败时记录 warning 日志（便于事后排查），
        调用方根据返回值决定是否向用户显示提示。
        """
        try:
            self.save()
            return True
        except (OSError, ValueError, DataSaveError) as e:
            logger.warning("保存学习进度失败: %s", e)
            return False
