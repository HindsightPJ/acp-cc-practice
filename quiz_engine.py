from typing import List, Dict, Any, Optional
import random
from datetime import datetime


class QuizEngine:
    def __init__(self, questions: List[Dict[str, Any]]) -> None:
        self.all_questions: List[Dict[str, Any]] = questions
        self.current_index: int = 0
        self.questions_queue: List[Dict[str, Any]] = []
        self.answers_record: List[Dict[str, Any]] = []
        self.stats: Dict[str, int] = {'correct': 0, 'wrong': 0, 'total': 0}
        self.exam_start_time: Optional[datetime] = None

    def start_practice_mode(self, shuffle: bool = False, category: Optional[str] = None) -> None:
        """启动练习模式"""
        self.questions_queue = list(self.all_questions)
        if shuffle:
            random.shuffle(self.questions_queue)

        self.current_index = 0
        self.answers_record = []
        self.stats = {'correct': 0, 'wrong': 0, 'total': 0}

    def start_exam_mode(self, question_count: int = 100, shuffle: bool = True) -> None:
        """启动模拟考试模式"""
        available = list(self.all_questions)
        if shuffle:
            random.shuffle(available)

        self.questions_queue = available[:question_count]
        self.current_index = 0
        self.answers_record = []
        self.stats = {'correct': 0, 'wrong': 0, 'total': 0}
        self.exam_start_time = datetime.now()

    def get_current_question(self) -> Optional[Dict[str, Any]]:
        """获取当前题目"""
        if 0 <= self.current_index < len(self.questions_queue):
            return self.questions_queue[self.current_index]
        return None

    def submit_answer(self, selected_letter: str) -> Optional[Dict[str, Any]]:
        """提交答案并判断对错"""
        current = self.get_current_question()
        if not current:
            return None

        # 多选题：排序后比较，确保顺序不影响判断
        selected_sorted = ''.join(sorted(selected_letter.upper()))
        answer_sorted = ''.join(sorted(current.get('answer', '')))
        is_correct = (selected_sorted == answer_sorted)

        result: Dict[str, Any] = {
            'queue_index': self.current_index,
            'question_number': current.get('number'),
            'selected': selected_letter.upper(),
            'correct_answer': current.get('answer'),
            'is_correct': is_correct,
            'question_content': current.get('content')[:50] + '...'
        }

        self.answers_record.append(result)
        self.stats['total'] += 1

        if is_correct:
            self.stats['correct'] += 1
        else:
            self.stats['wrong'] += 1

        return result

    def next_question(self) -> Optional[Dict[str, Any]]:
        """下一题"""
        self.current_index += 1
        return self.get_current_question()

    def prev_question(self) -> Optional[Dict[str, Any]]:
        """上一题"""
        if self.current_index > 0:
            self.current_index -= 1
        return self.get_current_question()

    def has_next(self) -> bool:
        """是否有下一题"""
        return self.current_index < len(self.questions_queue) - 1

    def has_prev(self) -> bool:
        """是否有上一题"""
        return self.current_index > 0

    def get_progress(self) -> Dict[str, Any]:
        """获取进度信息"""
        return {
            'current': self.current_index + 1,
            'total': len(self.questions_queue),
            'percentage': ((self.current_index + 1) / len(self.questions_queue)) * 100 if self.questions_queue else 0,
            'stats': self.stats
        }

    def get_wrong_answers(self) -> List[Dict[str, Any]]:
        """获取所有错误答案的题目。

        依赖 answers_record 中记录的 queue_index 反查 questions_queue，
        避免跳跃答题时索引错位。
        """
        wrong = []
        for r in self.answers_record:
            if r.get('is_correct'):
                continue
            idx = r.get('queue_index')
            if idx is None or not (0 <= idx < len(self.questions_queue)):
                continue
            wrong.append(self.questions_queue[idx])
        return wrong

    def record_exam_answer(self, queue_index: int, selected_letter: str) -> Optional[Dict[str, Any]]:
        """记录考试模式下的答题结果（支持跳跃答题）。

        与 submit_answer 不同，本方法不推进 current_index，仅把指定题号
        的作答结果写入 answers_record 并更新 stats。供考试模式交卷时批量
        评分使用。
        """
        if not (0 <= queue_index < len(self.questions_queue)):
            return None

        question = self.questions_queue[queue_index]
        selected_sorted = ''.join(sorted(selected_letter.upper()))
        answer_sorted = ''.join(sorted(question.get('answer', '')))
        is_correct = (selected_sorted == answer_sorted)

        result: Dict[str, Any] = {
            'queue_index': queue_index,
            'question_number': question.get('number'),
            'selected': selected_letter.upper(),
            'correct_answer': question.get('answer'),
            'is_correct': is_correct,
            'question_content': question.get('content', '')[:50] + '...'
        }

        self.answers_record.append(result)
        self.stats['total'] += 1
        if is_correct:
            self.stats['correct'] += 1
        else:
            self.stats['wrong'] += 1

        return result

    def get_exam_report(self) -> Optional[Dict[str, Any]]:
        """获取考试报告"""
        if self.exam_start_time is None:
            return None

        elapsed = (datetime.now() - self.exam_start_time).seconds
        minutes = elapsed // 60
        seconds = elapsed % 60

        return {
            'total_questions': len(self.questions_queue),
            'correct': self.stats['correct'],
            'wrong': self.stats['wrong'],
            'accuracy': (self.stats['correct'] / self.stats['total'] * 100) if self.stats['total'] > 0 else 0,
            'time_used': f"{minutes}分{seconds}秒",
            'wrong_questions': self.get_wrong_answers()
        }

    def get_review_questions(self) -> List[Dict[str, Any]]:
        """获取背题模式的题目列表"""
        return list(self.all_questions)
