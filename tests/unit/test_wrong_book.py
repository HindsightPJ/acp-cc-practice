"""wrong_book.py 单元测试。

覆盖范围：
- UI 层不直接访问 QuizEngine.stats（TD-15 后续修复）
- _show_practice_result 通过 get_stats() 读取统计
- P1-4: >=80% 正确率时只移除答对的错题，而非全部错题
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from ui.wrong_book import WrongBook  # pylint: disable=wrong-import-position


class _ForbidStatsAccess:
    """模拟 practice engine：直接访问 .stats 时抛异常。"""

    def __init__(self, stats, correct_nums=None):
        self._stats = stats
        self._correct_nums = correct_nums or set()

    def get_stats(self):
        return dict(self._stats)

    def get_correct_question_numbers(self):
        return set(self._correct_nums)

    def __getattr__(self, name):
        if name == 'stats':
            raise AttributeError("Direct access to engine.stats is forbidden")
        raise AttributeError(name)


def test_ui_source_no_direct_engine_internal_state_access():
    """ui 目录下任何模块都不应直接访问 QuizEngine 内部状态属性。"""
    ui_dir = Path(__file__).parent.parent.parent / 'ui'
    forbidden = (
        'engine.current_index',
        'engine.questions_queue',
        'engine.answers_record',
        'engine.stats',
        'engine.exam_start_time',
        'engine.all_questions',
        'practice_engine.current_index',
        'practice_engine.questions_queue',
        'practice_engine.answers_record',
        'practice_engine.stats',
        'practice_engine.exam_start_time',
        'practice_engine.all_questions',
    )
    for src_file in ui_dir.glob('*.py'):
        content = src_file.read_text(encoding='utf-8')
        for attr in forbidden:
            assert attr not in content, (
                f"{src_file.name} directly accesses {attr}"
            )


def test_show_practice_result_uses_get_stats(monkeypatch):
    """_show_practice_result 必须通过 get_stats() 读取统计。"""
    wb = WrongBook.__new__(WrongBook)
    wb.practice_engine = _ForbidStatsAccess(
        {'correct': 4, 'wrong': 6, 'total': 10}
    )
    wb.wrong_questions = []
    wb.progress = {'wrong_questions': []}
    wb.data_manager = MagicMock()
    wb.count_label = MagicMock()
    wb._practice_window = None  # A3 修复后新增的属性

    monkeypatch.setattr('tkinter.messagebox.showinfo', lambda *a, **k: None)
    monkeypatch.setattr('tkinter.messagebox.askyesno', lambda *a, **k: False)

    # 若代码仍直接访问 practice_engine.stats，会抛出 AttributeError
    wb._show_practice_result()


def test_show_practice_result_removes_only_correct(monkeypatch):
    """P1-4: >=80% 正确率时只移除本次答对的错题，保留答错的。

    此前 bug：遍历 self.wrong_questions 全部移除，包括答错的 20%。
    """
    wb = WrongBook.__new__(WrongBook)
    # 10 题，8 对 2 错 → 正确率 80%，触发移除分支
    wb.practice_engine = _ForbidStatsAccess(
        {'correct': 8, 'wrong': 2, 'total': 10},
        correct_nums={101, 102, 103, 104, 105, 106, 107, 108}  # 答对的 8 题
    )
    wb.progress = {'wrong_questions': [101, 102, 103, 104, 105, 106, 107, 108, 109, 110]}
    wb.data_manager = MagicMock()
    wb.count_label = MagicMock()
    wb._practice_window = None
    wb.wrong_questions = [  # 模拟 _get_wrong_questions_list 返回值
        {'number': n} for n in [101, 102, 103, 104, 105, 106, 107, 108, 109, 110]
    ]

    # 用户选"是"
    monkeypatch.setattr('tkinter.messagebox.askyesno', lambda *a, **k: True)
    # _populate_tree 和 _get_wrong_questions_list 会访问 tkinter，mock 掉
    monkeypatch.setattr(wb, '_populate_tree', lambda: None)
    monkeypatch.setattr(wb, '_get_wrong_questions_list', lambda: [])

    wb._show_practice_result()

    # 验证：progress['wrong_questions'] 应只剩答错的 2 题（109, 110）
    assert wb.progress['wrong_questions'] == [109, 110], (
        f"P1-4 回归：应只移除答对的 8 题，保留答错的 2 题，"
        f"实际剩余: {wb.progress['wrong_questions']}"
    )
    # 验证：data_manager.save_progress 被调用
    wb.data_manager.save_progress.assert_called_once_with(wb.progress)
