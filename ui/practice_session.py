"""练习会话管理器 - 封装题目练习的通用业务逻辑。

TD-Refactor: 从 PracticeMode 和 WrongBook 中提取的通用练习逻辑，
实现 UI 与业务逻辑解耦，消除重复代码。
"""

from typing import Any

from quiz_engine import QuizEngine
from app_state import AppState
from models import Question

from .selection import toggle_letter

# 与 models.Question.type 字段值保持一致（原 ui/constants.py，就近内联）
QUESTION_TYPE_SINGLE = "single"


class PracticeSession:
    """练习会话管理器 - 封装题目加载、选项选择、答案提交的通用逻辑。

    职责：
    - 管理练习状态（已答题、选中答案、当前题型）
    - 处理选项选择逻辑（单选/多选）
    - 提交答案并返回判题结果
    - 提供当前题目数据供 UI 层更新

    使用方式：
    - PracticeMode 持有 PracticeSession 实例
    - WrongBook 的错题练习也持有 PracticeSession 实例
    - UI 层负责渲染，PracticeSession 负责逻辑
    """

    def __init__(self, engine: QuizEngine, app_state: AppState) -> None:
        self.engine = engine
        self.app_state = app_state
        self.selected_answers: list[str] = []
        self.current_question_type = QUESTION_TYPE_SINGLE
        self.is_answered = False
        # 当前会话是否随机出题（快照导出用，供恢复时还原复选框状态）
        self._shuffle = False

    def load_current_question(self) -> Question | None:
        """加载当前题目，返回题目数据供 UI 更新。

        Returns:
            当前题目对象，如果没有题目则返回 None
        """
        return self.engine.get_current_question()

    def handle_option_click(self, letter: str, options_count: int) -> None:
        """处理选项点击，更新选中状态。

        Args:
            letter: 选项字母 (A-F)
            options_count: 当前题目的选项数量
        """
        if self.is_answered:
            return

        question = self.engine.get_current_question()
        if question is None:
            return

        card_idx = ord(letter) - ord("A")
        if card_idx >= options_count:
            return

        # 单选/多选切换语义与考试对齐（ui/selection.toggle_letter）：
        # 单选可再次点击取消，多选对称差切换
        is_multiple = self.current_question_type != QUESTION_TYPE_SINGLE
        self.selected_answers = sorted(
            toggle_letter(set(self.selected_answers), letter, is_multiple)
        )

    def is_option_selected(self, letter: str) -> bool:
        """检查选项是否被选中。"""
        return letter in self.selected_answers

    def submit_answer(self) -> dict[str, Any] | None:
        """提交答案，返回判题结果。

        Returns:
            判题结果字典，包含 is_correct, correct_answer 等；
            如果没有选中答案或没有当前题目，返回 None
        """
        if not self.selected_answers:
            return None

        question = self.engine.get_current_question()
        if question is None:
            return None

        # P2-1: 在 engine.submit_answer 写入前判断是否首次提交，
        # 避免切走再切回重新提交时 increment_practice_stats 双倍计数
        current_idx = self.engine.get_current_index()
        is_first_submission = not self.engine.is_answered(current_idx)

        answer_str = "".join(sorted(self.selected_answers))
        result = self.engine.submit_answer(answer_str)
        if result is None:
            return None

        self.is_answered = True

        # P2-1: 仅首次提交该题时更新统计与错题本，重复提交只刷新 UI 显示
        if is_first_submission:
            # 记录错题
            if not result["is_correct"]:
                q_num = question.number
                if not self.app_state.is_wrong_question(q_num):
                    self.app_state.add_wrong_question(q_num)

            # 更新练习统计
            self.app_state.increment_practice_stats(result["is_correct"])

        return result

    def get_question_type(self, question: Question) -> str:
        """获取题目类型，更新内部状态并返回。"""
        self.current_question_type = question.type
        return self.current_question_type

    def reset_selection(self) -> None:
        """重置选中状态。"""
        self.selected_answers = []
        self.is_answered = False

    def reset_session(self, shuffle: bool = False) -> None:
        """重置练习会话。

        Args:
            shuffle: 是否随机出题
        """
        self.engine.start_practice_mode(shuffle=shuffle)
        self._shuffle = shuffle
        self.reset_selection()

    # ---------- 会话快照（进度恢复） ----------

    def export_state(self) -> dict[str, Any]:
        """导出会话快照：引擎快照（队列题号/索引/答案）+ shuffle 状态。

        队列按题号持久化（见 QuizEngine.get_snapshot）；shuffle 由会话层
        补充，供恢复时还原复选框显示。
        """
        state = self.engine.get_snapshot()
        state["shuffle"] = self._shuffle
        return state

    def restore_state(self, state: dict[str, Any]) -> bool:
        """从快照恢复会话（供应用重启后继续上次练习）。

        校验失败（题库版本变化 / 结构损坏 / 索引越界）返回 False，
        调用方应回退到全新会话，不抛异常。shuffle 仅在引擎恢复成功后还原。
        """
        if self.engine.restore_snapshot(state):
            self._shuffle = bool(state.get("shuffle", False))
            return True
        return False

    def get_stats(self) -> dict[str, Any]:
        """获取当前练习统计。"""
        return self.engine.get_stats()

    def has_next(self) -> bool:
        """是否有下一题。"""
        return self.engine.has_next()

    def has_prev(self) -> bool:
        """是否有上一题。"""
        return self.engine.has_prev()

    def next_question(self) -> None:
        """移动到下一题。"""
        self.engine.next_question()

    def prev_question(self) -> None:
        """移动到上一题。"""
        self.engine.prev_question()

    def get_correct_question_numbers(self) -> list[int]:
        """获取本次练习中答对的题号列表。"""
        return list(self.engine.get_correct_question_numbers())
