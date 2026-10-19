from typing import Any
import random
import time

from models import Question


class QuizEngine:
    def __init__(self, questions: list[Question]) -> None:
        self.all_questions: list[Question] = list(questions)
        self.current_index: int = 0
        self.questions_queue: list[Question] = []
        self.answers_record: dict[int, dict[str, Any]] = {}
        self.exam_start_time: float | None = None

    def start_practice_mode(self, shuffle: bool = False) -> None:
        """启动练习模式"""
        self.questions_queue = list(self.all_questions)
        if shuffle:
            random.shuffle(self.questions_queue)

        self.current_index = 0
        self.answers_record = {}

    def start_exam_mode(self, question_count: int = 100, shuffle: bool = True) -> None:
        """启动模拟考试模式"""
        available = list(self.all_questions)
        if shuffle:
            random.shuffle(available)

        self.questions_queue = available[:question_count]
        self.current_index = 0
        self.answers_record = {}
        self.exam_start_time = time.monotonic()

    def get_current_question(self) -> Question | None:
        """获取当前题目"""
        if 0 <= self.current_index < len(self.questions_queue):
            return self.questions_queue[self.current_index]
        return None

    def _grade_answer(self, selected: str, correct: str) -> bool:
        """判断答案是否正确（多选题排序后比较）。"""
        selected_sorted = "".join(sorted(selected.upper()))
        correct_sorted = "".join(sorted(correct))
        # 空答案不应判为正确
        return bool(correct_sorted) and (selected_sorted == correct_sorted)

    def _build_result_record(
        self, queue_index: int, question: Question, selected: str, is_correct: bool
    ) -> dict[str, Any]:
        """构造答题结果字典。"""
        return {
            "queue_index": queue_index,
            "question_number": question.number,
            "selected": selected.upper(),
            "correct_answer": question.answer,
            "is_correct": is_correct,
            "question_content": question.content[:50] + "...",
        }

    def submit_answer(self, selected_letter: str) -> dict[str, Any] | None:
        """提交答案并判断对错（记录到当前索引）"""
        if self.get_current_question() is None:
            return None
        return self.record_exam_answer(self.current_index, selected_letter)

    def next_question(self) -> Question | None:
        """下一题"""
        self.current_index += 1
        return self.get_current_question()

    def prev_question(self) -> Question | None:
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

    def get_progress(self) -> dict[str, Any]:
        """获取进度信息（TD-15: stats 返回副本，避免 UI 意外修改内部状态）。"""
        return {
            "current": self.current_index + 1,
            "total": len(self.questions_queue),
            "percentage": ((self.current_index + 1) / len(self.questions_queue)) * 100
            if self.questions_queue
            else 0,
            "stats": self.get_stats(),
        }

    def get_stats(self) -> dict[str, int]:
        """获取统计信息（从 answers_record 重新计算，确保跳跃答题不重复计数）。"""
        total = len(self.answers_record)
        correct = sum(1 for r in self.answers_record.values() if r.get("is_correct"))
        return {"correct": correct, "wrong": total - correct, "total": total}

    def get_current_index(self) -> int:
        """获取当前题目索引（TD-15: 显式接口，替代 UI 直接读 engine.current_index）。"""
        return self.current_index

    def set_current_index(self, idx: int) -> None:
        """设置当前题目索引（TD-15: 显式接口，供 UI 跳转答题用）。

        不做边界检查，与原直接赋值行为一致；调用方负责边界判断。
        """
        self.current_index = idx

    def queue_length(self) -> int:
        """获取题目队列长度（TD-15: 显式接口，替代 len(engine.questions_queue)）。"""
        return len(self.questions_queue)

    def is_answered(self, index: int) -> bool:
        """指定索引的题目是否已作答（TD-15: 显式接口，替代直接访问 answers_record）。

        P2-1: 供 PracticeSession 判断是否首次提交，避免重复计数。
        """
        return index in self.answers_record

    def get_question_at(self, index: int) -> Question | None:
        """获取指定索引的题目（TD-15: 显式接口，替代 engine.questions_queue[i]）。

        Returns:
            题目对象；索引越界返回 None
        """
        if 0 <= index < len(self.questions_queue):
            return self.questions_queue[index]
        return None

    def set_questions_queue(self, questions: list[Question]) -> None:
        """替换题目队列（TD-15: 显式接口，供 review_mode 加载错题列表用）。

        内部做浅拷贝，避免外部修改传入的 list 影响内部状态。
        若新队列短于 current_index，自动将 current_index 限制到末尾。
        """
        self.questions_queue = list(questions)
        if self.current_index >= len(self.questions_queue):
            self.current_index = max(0, len(self.questions_queue) - 1)

    def get_correct_question_numbers(self) -> set[int]:
        """获取本次练习/考试中答对的题号集合（P1-4: 供 WrongBook 移除已掌握错题用）。

        Returns:
            答对的题号集合（question_number 字段值），未作答或答错的不包含在内
        """
        return {
            r["question_number"]
            for r in self.answers_record.values()
            if r.get("is_correct") and r.get("question_number") is not None
        }

    def record_exam_answer(self, queue_index: int, selected_letter: str) -> dict[str, Any] | None:
        """记录考试模式下的答题结果（支持跳跃答题，覆盖更新而非追加）。

        与 submit_answer 不同，本方法不推进 current_index，仅把指定题号
        的作答结果写入 answers_record。供考试模式交卷时批量评分使用。
        stats 由 get_stats 从 answers_record 重新计算，确保同一题改答案
        不会重复计数。
        """
        if not (0 <= queue_index < len(self.questions_queue)):
            return None

        question = self.questions_queue[queue_index]
        is_correct = self._grade_answer(selected_letter, question.answer)
        result = self._build_result_record(queue_index, question, selected_letter, is_correct)

        self.answers_record[queue_index] = result

        return result

    def has_answers(self) -> bool:
        """是否存在任何作答记录（TD-15: 显式接口，替代直接访问 answers_record）。"""
        return bool(self.answers_record)

    def get_snapshot(self) -> dict[str, Any]:
        """导出可持久化快照（练习进度恢复用）。

        队列按题号持久化——随机出题后索引只对本次队列有效，恢复时按
        题号重建才能保证 index/answers 与题目对应。队列完成时 current_index
        可能越界（next 触发 on_finish），钳到末题保证快照始终可通过
        restore_snapshot 的越界校验。
        """
        queue_len = len(self.questions_queue)
        index = self.current_index
        return {
            "queue": [q.number for q in self.questions_queue],
            "index": index if index < queue_len else max(queue_len - 1, 0),
            "answers": {
                str(idx): record.get("selected", "") for idx, record in self.answers_record.items()
            },
        }

    def restore_snapshot(self, state: dict[str, Any]) -> bool:
        """从 get_snapshot 的快照恢复（练习进度恢复用）。

        结构损坏 / 题库变化（题号缺失或数量不符）/ 索引越界均整体拒绝，
        返回 False 且不产生任何状态修改；全部校验通过才重建队列并按
        record_exam_answer 重新判分写入 answers_record。

        Returns:
            恢复成功返回 True
        """
        try:
            queue_nums = state.get("queue")
            if not isinstance(queue_nums, list) or not queue_nums:
                return False
            if not all(isinstance(n, int) and not isinstance(n, bool) for n in queue_nums):
                return False
            by_number = {q.number: q for q in self.all_questions}
            queue = [by_number[n] for n in queue_nums if n in by_number]
            # 数量不符说明题库已变化（升级/试用降级），放弃恢复保证一致性
            if len(queue) != len(queue_nums):
                return False

            index = state.get("index")
            answers = state.get("answers")
            if (
                not isinstance(index, int)
                or isinstance(index, bool)
                or not isinstance(answers, dict)
            ):
                return False
            if not 0 <= index < len(queue):
                return False

            # 先完整解析答案表（任何非法条目整体拒绝），再落状态
            parsed: list[tuple[int, str]] = []
            for key, selected in answers.items():
                idx = int(key)
                if not (isinstance(selected, str) and 0 <= idx < len(queue)):
                    return False
                parsed.append((idx, selected))

            self.set_questions_queue(queue)
            self.set_current_index(index)
            self.answers_record = {}
            for idx, selected in parsed:
                self.record_exam_answer(idx, selected)
            return True
        except (TypeError, ValueError):
            return False

    def get_exam_elapsed_seconds(self) -> int | None:
        """获取考试已进行秒数（TD-15: 显式接口，替代 UI 直接读取 exam_start_time）。

        Returns:
            若未启动考试模式返回 None；否则返回从开始到调用时的整秒数。
        """
        if self.exam_start_time is None:
            return None
        return int(time.monotonic() - self.exam_start_time)

    def get_exam_report(self) -> dict[str, Any] | None:
        """获取考试报告"""
        if self.exam_start_time is None:
            return None

        elapsed = self.get_exam_elapsed_seconds()
        if elapsed is None:
            return None
        minutes = elapsed // 60
        seconds = elapsed % 60

        stats = self.get_stats()
        # 错题明细按队列序排列，附用户作答（报告回顾页展示"已选 vs 正确"用）
        wrong_records: list[dict[str, Any]] = []
        for idx in sorted(self.answers_record):
            r = self.answers_record[idx]
            if r.get("is_correct"):
                continue
            queue_index = r.get("queue_index")
            if queue_index is None or not (0 <= queue_index < len(self.questions_queue)):
                continue
            wrong_records.append(
                {
                    "question": self.questions_queue[queue_index],
                    "selected": str(r.get("selected", "")),
                }
            )
        return {
            "total_questions": len(self.questions_queue),
            "correct": stats["correct"],
            "wrong": stats["wrong"],
            "accuracy": (stats["correct"] / stats["total"] * 100) if stats["total"] > 0 else 0,
            "time_used": f"{minutes}分{seconds}秒",
            "wrong_questions": [w["question"] for w in wrong_records],
            "wrong_records": wrong_records,
        }
