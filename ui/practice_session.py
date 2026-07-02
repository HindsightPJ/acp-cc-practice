"""练习会话管理器 - 封装题目练习的通用业务逻辑。

TD-Refactor: 从 PracticeMode 和 WrongBook 中提取的通用练习逻辑，
实现 UI 与业务逻辑解耦，消除重复代码。
"""

from typing import List, Dict, Any, Optional

from quiz_engine import QuizEngine
from app_state import AppState
from models import Question


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
        self.selected_answers: List[str] = []
        self.current_question_type = "single"
        self.is_answered = False

    def load_current_question(self) -> Optional[Question]:
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

        if self.current_question_type == "single":
            # 单选题：只选中当前选项
            self.selected_answers = [letter]
        else:
            # 多选题：切换当前选项
            if letter in self.selected_answers:
                self.selected_answers.remove(letter)
            else:
                self.selected_answers.append(letter)
                self.selected_answers.sort()

    def is_option_selected(self, letter: str) -> bool:
        """检查选项是否被选中。"""
        return letter in self.selected_answers

    def submit_answer(self) -> Optional[Dict[str, Any]]:
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

        answer_str = "".join(sorted(self.selected_answers))
        result = self.engine.submit_answer(answer_str)
        if result is None:
            return None

        self.is_answered = True

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
        self.reset_selection()

    def get_progress(self) -> Dict[str, Any]:
        """获取当前练习进度。"""
        return self.engine.get_progress()

    def get_stats(self) -> Dict[str, Any]:
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

    def get_correct_question_numbers(self) -> List[int]:
        """获取本次练习中答对的题号列表。"""
        return self.engine.get_correct_question_numbers()
