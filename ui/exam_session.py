"""ExamSession - 考试模式的业务逻辑封装。

P3: 将 ExamMode 中分散的选项选择、答案记录逻辑集中到这里，
使考试模式也能复用与练习模式相同的选项处理思路，并便于统一键盘处理。
"""

from typing import Dict, List, Optional, Set

from quiz_engine import QuizEngine
from models import Question


class ExamSession:
    """考试模式会话：管理当前题目选项切换、已答答案与标记状态。"""

    def __init__(self, engine: QuizEngine) -> None:
        self.engine = engine
        self.answers: Dict[int, str] = {}
        self.marked: Set[int] = set()

    def get_current_question(self) -> Optional[Question]:
        """获取当前题目。"""
        return self.engine.get_current_question()

    def get_current_index(self) -> int:
        """获取当前题号索引。"""
        return self.engine.get_current_index()

    def get_current_selected(self) -> str:
        """获取当前题目已选答案（排序后的字母串）。"""
        return self.answers.get(self.get_current_index(), "")

    def is_multiple_choice(self) -> bool:
        """当前题目是否为多选题。"""
        question = self.get_current_question()
        if question is None:
            return False
        return question.type == "multiple"

    def select_option(self, letter: str) -> Optional[str]:
        """切换当前题目的选项选择状态。

        Args:
            letter: 选项字母 A-F

        Returns:
            当前题目最终选中的字母串（排序后），若题目不存在返回 None
        """
        question = self.get_current_question()
        if question is None:
            return None

        idx = ord(letter) - ord("A")
        if idx < 0 or idx >= len(question.options):
            return None

        current_idx = self.get_current_index()
        current = set(self.answers.get(current_idx, ""))

        if self.is_multiple_choice():
            if letter in current:
                current.discard(letter)
            else:
                current.add(letter)
        else:
            current = {letter}

        selected = "".join(sorted(current))
        if selected:
            self.answers[current_idx] = selected
        elif current_idx in self.answers:
            del self.answers[current_idx]

        return selected

    def record_answer(self) -> bool:
        """记录当前题目的答案到 QuizEngine（用于交卷评分）。

        Returns:
            是否成功记录
        """
        question = self.get_current_question()
        if question is None:
            return False

        selected = self.answers.get(self.get_current_index(), "")
        self.engine.record_exam_answer(self.get_current_index(), selected)
        return True

    def record_all_answers(self) -> None:
        """在交卷前把所有已选答案写入 QuizEngine。"""
        original_index = self.engine.get_current_index()
        for idx, selected in self.answers.items():
            self.engine.set_current_index(idx)
            self.engine.record_exam_answer(idx, selected)
        self.engine.set_current_index(original_index)

    def toggle_mark(self) -> int:
        """切换当前题目的标记状态，返回当前索引。"""
        idx = self.get_current_index()
        if idx in self.marked:
            self.marked.remove(idx)
        else:
            self.marked.add(idx)
        return idx

    def has_answer(self, idx: int) -> bool:
        """指定索引的题目是否已作答。"""
        return idx in self.answers

    def is_marked(self, idx: int) -> bool:
        """指定索引的题目是否已标记。"""
        return idx in self.marked
