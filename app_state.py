"""应用状态对象（TD-30）：解耦 UI 与持久化状态管理。

UI 层通过 AppState 读写学习进度，不再直接调用 data_manager.save_progress，
也不再直接访问原始 progress dict。
"""

import logging
import random
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

    # ---------- 考试卡组（组卷覆盖保证） ----------
    def draw_exam_questions(self, count: int, all_numbers: list[int]) -> list[int]:
        """从持久化卡组顺次抽 count 个题号组卷（考试模式覆盖保证）。

        卡组语义：progress.json 持久化一份整库洗牌牌堆，每次考试从牌堆
        顺次抽 count 张；牌堆耗尽即整库重洗进入下一周期——保证每个周期内
        全库每题至少出现一次，避免纯随机抽样的"有的题长期不出现"。

        - 同一场考试内绝不重复：中途重洗时排除本场已抽题号
          （前提 count ≤ 全库题数，调用方保证，此处钳位兜底）
        - 题库升级/降级（卡组题号不在当前库中）→ 丢弃旧卡组整库重洗
        - 只改内存，随下次 save_safe 落盘（调用方开考后自行 save_safe）

        Args:
            count: 组卷题数；超过全库题数时钳位为全库题数
            all_numbers: 当前题库全部题号（判定题库变化用）

        Returns:
            本场考试的题号列表（与卡组顺序一致，UI 直接作队列）
        """
        bank = list(dict.fromkeys(all_numbers))  # 去重保序，防御异常数据
        if not bank or count <= 0:
            return []
        count = min(count, len(bank))

        deck = self._progress.get("exam_deck")
        if (
            not isinstance(deck, list)
            or not deck
            or not all(isinstance(n, int) and not isinstance(n, bool) for n in deck)
            or not set(deck) <= set(bank)
        ):
            deck = bank.copy()
            random.shuffle(deck)

        drawn: list[int] = []
        while len(drawn) < count:
            if not deck:
                # 周期耗尽：整库重洗，排除本场已抽（同场不重复）
                deck = [n for n in bank if n not in drawn]
                random.shuffle(deck)
            take = deck[: count - len(drawn)]
            drawn.extend(take)
            deck = deck[len(take) :]

        self._progress["exam_deck"] = deck
        return drawn

    # ---------- 练习会话快照（进度恢复） ----------
    def get_practice_progress(self) -> dict[str, Any]:
        """返回练习会话快照（无/格式异常时返回空 dict）。"""
        data = self._progress.get("practice_progress")
        return dict(data) if isinstance(data, dict) else {}

    def set_practice_progress(self, data: dict[str, Any]) -> None:
        """写入练习会话快照（随下次 save_safe 一并落盘）。"""
        self._progress["practice_progress"] = data

    # ---------- UI 主题模式 ----------
    # 合法值与 ui.constants.THEME_MODES 保持一致；此处内联字面量，
    # 避免状态层反向依赖 UI 层（ui 包 import 即引入 tkinter）
    _VALID_THEME_MODES = ("light", "dark")

    def get_theme_mode(self) -> str:
        """返回主题模式（"light"/"dark"），缺失或非法值 fail-safe 回 "light"。"""
        mode = self._progress.get("theme_mode", "light")
        if mode not in self._VALID_THEME_MODES:
            logger.warning("progress.json 中 theme_mode 非法: %r，回退 light", mode)
            return "light"
        return str(mode)

    def set_theme_mode(self, mode: str) -> None:
        """写入主题模式（随下次 save_safe 一并落盘）。"""
        self._progress["theme_mode"] = mode

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
