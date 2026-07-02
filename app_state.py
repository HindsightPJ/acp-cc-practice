"""应用状态对象（TD-30）：解耦 UI 与持久化状态管理。

UI 层通过 AppState 读写学习进度，不再直接调用 data_manager.save_progress，
也不再直接访问原始 progress dict。
"""

from typing import Any, Dict, List, Optional

from data_manager import DataManager, DataSaveError


class AppState:
    """封装学习进度及其持久化操作。

    提供类型安全的方法访问错题、收藏、练习统计、考试历史等数据，
    所有修改最终通过 data_manager.save_progress 落盘。
    """

    def __init__(
        self, data_manager: DataManager, progress: Optional[Dict[str, Any]] = None
    ) -> None:
        self._data_manager = data_manager
        self._progress: Dict[str, Any] = progress if progress is not None else {}
        self._ensure_defaults()

    def _ensure_defaults(self) -> None:
        """确保进度字典包含所有必需字段。"""
        self._progress.setdefault("wrong_questions", [])
        self._progress.setdefault("practice_stats", {"correct": 0, "wrong": 0, "total": 0})
        self._progress.setdefault("exam_history", [])
        self._progress.setdefault("favorites", [])
        self._progress.setdefault("settings", {})

    # ---------- 练习统计 ----------
    def get_practice_stats(self) -> Dict[str, int]:
        return dict(self._progress.get("practice_stats", {"correct": 0, "wrong": 0, "total": 0}))

    def increment_practice_stats(self, is_correct: bool) -> None:
        stats = self._progress.setdefault("practice_stats", {"correct": 0, "wrong": 0, "total": 0})
        stats["total"] = stats.get("total", 0) + 1
        if is_correct:
            stats["correct"] = stats.get("correct", 0) + 1
        else:
            stats["wrong"] = stats.get("wrong", 0) + 1

    # ---------- 错题 ----------
    def get_wrong_questions(self) -> List[int]:
        return list(self._progress.get("wrong_questions", []))

    def add_wrong_question(self, q_num: int) -> None:
        wrong = self._progress.setdefault("wrong_questions", [])
        if q_num not in wrong:
            wrong.append(q_num)

    def remove_wrong_question(self, q_num: int) -> None:
        wrong = self._progress.get("wrong_questions", [])
        if q_num in wrong:
            wrong.remove(q_num)

    def set_wrong_questions(self, q_nums: List[int]) -> None:
        self._progress["wrong_questions"] = list(q_nums)

    def is_wrong_question(self, q_num: int) -> bool:
        return q_num in self._progress.get("wrong_questions", [])

    # ---------- 收藏 ----------
    def get_favorites(self) -> List[int]:
        return list(self._progress.get("favorites", []))

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
    def get_exam_history(self) -> List[Dict[str, Any]]:
        return list(self._progress.get("exam_history", []))

    def add_exam_history(self, entry: Dict[str, Any]) -> None:
        history = self._progress.setdefault("exam_history", [])
        history.append(entry)
        # 仅保留最近 20 条，避免进度文件无限增长
        self._progress["exam_history"] = history[-20:]

    # ---------- 设置 ----------
    def get_setting(self, key: str, default: Any = None) -> Any:
        settings = self._progress.setdefault("settings", {})
        return settings.get(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        settings = self._progress.setdefault("settings", {})
        settings[key] = value

    # ---------- 持久化 ----------
    def save(self) -> None:
        """立即保存进度到 data_manager。"""
        self._data_manager.save_progress(self._progress)

    def save_safe(self) -> None:
        """保存进度并静默捕获保存错误，适用于销毁等不可阻塞的场景。"""
        try:
            self.save()
        except (OSError, ValueError, DataSaveError):
            pass
