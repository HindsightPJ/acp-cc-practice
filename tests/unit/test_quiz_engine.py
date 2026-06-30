"""quiz_engine.py 单元测试。

覆盖范围：
- 初始化与状态重置
- 练习模式 / 考试模式启动
- 答题判定（单选/多选、顺序无关）
- 导航（next/prev/has_next/has_prev）
- 进度计算
- 错题反查（queue_index 索引机制）
- 考试模式跳跃答题（record_exam_answer）
- 考试报告生成
- 背题模式列表
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from quiz_engine import QuizEngine  # pylint: disable=wrong-import-position


# ---------- 辅助函数 ----------

def make_single_question(number: int, answer: str = 'A') -> dict:
    """构造单选题。"""
    return {
        'number': number,
        'content': f'单选题 {number} 内容',
        'options': [
            {'letter': 'A', 'text': '选项 A'},
            {'letter': 'B', 'text': '选项 B'},
            {'letter': 'C', 'text': '选项 C'},
            {'letter': 'D', 'text': '选项 D'},
        ],
        'answer': answer,
        'type': 'single',
        'explanation': f'解析 {number}',
    }


def make_multi_question(number: int, answer: str = 'ABC') -> dict:
    """构造多选题。"""
    return {
        'number': number,
        'content': f'多选题 {number} 内容',
        'options': [
            {'letter': 'A', 'text': '选项 A'},
            {'letter': 'B', 'text': '选项 B'},
            {'letter': 'C', 'text': '选项 C'},
            {'letter': 'D', 'text': '选项 D'},
        ],
        'answer': answer,
        'type': 'multiple',
        'explanation': f'解析 {number}',
    }


def make_questions(count: int, multi_at: tuple = ()) -> list:
    """构造 count 道题，multi_at 指定的题号为多选题。"""
    qs = []
    for i in range(1, count + 1):
        if i in multi_at:
            qs.append(make_multi_question(i))
        else:
            qs.append(make_single_question(i))
    return qs


# ---------- Fixtures ----------

@pytest.fixture
def sample_questions():
    """10 道题：第 3、7 题为多选，其余单选。"""
    return make_questions(10, multi_at=(3, 7))


@pytest.fixture
def engine(sample_questions):
    """已加载 sample_questions 的 QuizEngine。"""
    return QuizEngine(sample_questions)


# ---------- __init__ 测试 ----------

def test_init_empty_questions():
    """空题库初始化不应报错。"""
    eng = QuizEngine([])
    assert eng.all_questions == []
    assert eng.current_index == 0
    assert eng.questions_queue == []
    assert eng.answers_record == []
    assert eng.stats == {'correct': 0, 'wrong': 0, 'total': 0}
    assert eng.exam_start_time is None


def test_init_with_questions(sample_questions):
    """有题库时初始化应保存到 all_questions，但不填充 queue。"""
    eng = QuizEngine(sample_questions)
    assert len(eng.all_questions) == 10
    assert eng.questions_queue == []  # 未调用 start_*_mode 前 queue 为空


# ---------- start_practice_mode 测试 ----------

def test_start_practice_mode_no_shuffle(engine, sample_questions):
    """无 shuffle 时 queue 应与 all_questions 顺序一致。"""
    engine.start_practice_mode(shuffle=False)
    assert len(engine.questions_queue) == 10
    assert engine.questions_queue[0]['number'] == 1
    assert engine.questions_queue[9]['number'] == 10
    assert engine.current_index == 0
    assert engine.answers_record == []
    assert engine.stats == {'correct': 0, 'wrong': 0, 'total': 0}


def test_start_practice_mode_with_shuffle(engine, sample_questions):
    """shuffle 时 queue 应包含相同题目但顺序可能不同。"""
    engine.start_practice_mode(shuffle=True)
    assert len(engine.questions_queue) == 10
    # 题目集合相同（按 number 比较）
    original_numbers = {q['number'] for q in sample_questions}
    shuffled_numbers = {q['number'] for q in engine.questions_queue}
    assert original_numbers == shuffled_numbers


def test_start_practice_mode_resets_state(engine):
    """start_practice_mode 应重置 stats 和 answers_record。"""
    # 先制造一些作答记录
    engine.start_practice_mode(shuffle=False)
    engine.submit_answer('A')
    engine.next_question()
    engine.submit_answer('B')
    assert engine.stats['total'] == 2

    # 重新开始应清空
    engine.start_practice_mode(shuffle=False)
    assert engine.stats == {'correct': 0, 'wrong': 0, 'total': 0}
    assert engine.answers_record == []
    assert engine.current_index == 0


def test_start_practice_mode_category_dead_param(engine):
    """category 参数当前未实现筛选（TD-14），传值不应影响 queue。"""
    engine.start_practice_mode(shuffle=False, category='some_category')
    assert len(engine.questions_queue) == 10  # 未筛选


def test_start_practice_mode_empty_questions():
    """空题库启动练习模式不应报错。"""
    eng = QuizEngine([])
    eng.start_practice_mode(shuffle=False)
    assert eng.questions_queue == []


# ---------- start_exam_mode 测试 ----------

def test_start_exam_mode_limit_count(engine):
    """考试模式应截取指定数量的题目。"""
    engine.start_exam_mode(question_count=5, shuffle=False)
    assert len(engine.questions_queue) == 5


def test_start_exam_mode_count_exceeds_available(engine):
    """题量超过题库总数时取全部。"""
    engine.start_exam_mode(question_count=100, shuffle=False)
    assert len(engine.questions_queue) == 10


def test_start_exam_mode_sets_start_time(engine):
    """考试模式应设置 exam_start_time。"""
    assert engine.exam_start_time is None
    engine.start_exam_mode(question_count=5, shuffle=False)
    assert engine.exam_start_time is not None


def test_start_exam_mode_resets_state(engine):
    """考试模式应重置状态。"""
    engine.start_practice_mode(shuffle=False)
    engine.submit_answer('A')
    engine.start_exam_mode(question_count=5, shuffle=False)
    assert engine.stats == {'correct': 0, 'wrong': 0, 'total': 0}
    assert engine.answers_record == []
    assert engine.current_index == 0


def test_start_exam_mode_with_shuffle(engine, sample_questions):
    """考试模式 shuffle 应保持题目集合不变。"""
    engine.start_exam_mode(question_count=5, shuffle=True)
    assert len(engine.questions_queue) == 5
    original_numbers = {q['number'] for q in sample_questions}
    exam_numbers = {q['number'] for q in engine.questions_queue}
    assert exam_numbers.issubset(original_numbers)


# ---------- get_current_question 测试 ----------

def test_get_current_question_initial(engine):
    """启动后应返回第一题。"""
    engine.start_practice_mode(shuffle=False)
    q = engine.get_current_question()
    assert q is not None
    assert q['number'] == 1


def test_get_current_question_out_of_bounds(engine):
    """索引越界应返回 None。"""
    engine.start_practice_mode(shuffle=False)
    engine.current_index = 10  # 越界
    assert engine.get_current_question() is None


def test_get_current_question_empty_queue(engine):
    """空 queue 时应返回 None。"""
    assert engine.get_current_question() is None


def test_get_current_question_negative_index(engine):
    """负索引应返回 None（边界检查 0 <= index）。"""
    engine.start_practice_mode(shuffle=False)
    engine.current_index = -1
    assert engine.get_current_question() is None


# ---------- submit_answer 测试 ----------

def test_submit_single_correct(engine):
    """单选答对 → is_correct=True。"""
    engine.start_practice_mode(shuffle=False)
    result = engine.submit_answer('A')
    assert result is not None
    assert result['is_correct'] is True
    assert result['correct_answer'] == 'A'


def test_submit_single_wrong(engine):
    """单选答错 → is_correct=False。"""
    engine.start_practice_mode(shuffle=False)
    result = engine.submit_answer('B')
    assert result is not None
    assert result['is_correct'] is False
    assert result['correct_answer'] == 'A'


def test_submit_multi_correct_order_independent(engine):
    """多选题答案顺序不影响判定（'BCA' == 'ABC'）。"""
    engine.start_practice_mode(shuffle=False)
    engine.current_index = 2  # 第 3 题是多选，答案 ABC
    result = engine.submit_answer('BCA')
    assert result is not None
    assert result['is_correct'] is True


def test_submit_multi_wrong(engine):
    """多选答错 → is_correct=False。"""
    engine.start_practice_mode(shuffle=False)
    engine.current_index = 2  # 第 3 题，答案 ABC
    result = engine.submit_answer('AB')
    assert result is not None
    assert result['is_correct'] is False


def test_submit_answer_lowercase_input(engine):
    """小写输入应自动转大写比较。"""
    engine.start_practice_mode(shuffle=False)
    result = engine.submit_answer('a')
    assert result is not None
    assert result['is_correct'] is True
    assert result['selected'] == 'A'


def test_submit_answer_no_current_question(engine):
    """无当前题时返回 None。"""
    # 未 start 时 queue 为空
    assert engine.submit_answer('A') is None


def test_submit_answer_updates_stats_correct(engine):
    """答对应使 correct+1、total+1。"""
    engine.start_practice_mode(shuffle=False)
    engine.submit_answer('A')
    assert engine.stats == {'correct': 1, 'wrong': 0, 'total': 1}


def test_submit_answer_updates_stats_wrong(engine):
    """答错应使 wrong+1、total+1。"""
    engine.start_practice_mode(shuffle=False)
    engine.submit_answer('B')
    assert engine.stats == {'correct': 0, 'wrong': 1, 'total': 1}


def test_submit_answer_records_in_answers_record(engine):
    """每次提交应追加到 answers_record。"""
    engine.start_practice_mode(shuffle=False)
    engine.submit_answer('A')
    engine.next_question()
    engine.submit_answer('B')
    assert len(engine.answers_record) == 2
    assert engine.answers_record[0]['queue_index'] == 0
    assert engine.answers_record[1]['queue_index'] == 1


def test_submit_answer_result_fields(engine):
    """返回结果应包含完整字段。"""
    engine.start_practice_mode(shuffle=False)
    result = engine.submit_answer('A')
    assert 'queue_index' in result
    assert 'question_number' in result
    assert 'selected' in result
    assert 'correct_answer' in result
    assert 'is_correct' in result
    assert 'question_content' in result


# ---------- next_question / prev_question 测试 ----------

def test_next_question_advances(engine):
    """next_question 应推进索引并返回下一题。"""
    engine.start_practice_mode(shuffle=False)
    q = engine.next_question()
    assert q is not None
    assert q['number'] == 2
    assert engine.current_index == 1


def test_next_question_at_end(engine):
    """最后一题 next 应返回 None。"""
    engine.start_practice_mode(shuffle=False)
    engine.current_index = 9  # 最后一题
    q = engine.next_question()
    assert q is None
    assert engine.current_index == 10  # 越界


def test_prev_question_decreases(engine):
    """prev_question 应回退索引。"""
    engine.start_practice_mode(shuffle=False)
    engine.current_index = 5
    q = engine.prev_question()
    assert q is not None
    assert q['number'] == 5  # index 4 → 第 5 题
    assert engine.current_index == 4


def test_prev_question_at_start(engine):
    """第一题 prev 不应越界。"""
    engine.start_practice_mode(shuffle=False)
    q = engine.prev_question()
    assert q is not None
    assert q['number'] == 1
    assert engine.current_index == 0


def test_has_next(engine):
    """中间题应有下一题。"""
    engine.start_practice_mode(shuffle=False)
    engine.current_index = 4
    assert engine.has_next() is True


def test_has_next_at_end(engine):
    """最后一题应无下一题。"""
    engine.start_practice_mode(shuffle=False)
    engine.current_index = 9
    assert engine.has_next() is False


def test_has_prev_at_start(engine):
    """第一题应无上一题。"""
    engine.start_practice_mode(shuffle=False)
    assert engine.has_prev() is False


def test_has_prev(engine):
    """中间题应有上一题。"""
    engine.start_practice_mode(shuffle=False)
    engine.current_index = 5
    assert engine.has_prev() is True


# ---------- get_progress 测试 ----------

def test_get_progress_initial(engine):
    """初始进度应为 1/10。"""
    engine.start_practice_mode(shuffle=False)
    progress = engine.get_progress()
    assert progress['current'] == 1
    assert progress['total'] == 10
    assert progress['percentage'] == 10.0


def test_get_progress_midway(engine):
    """中间进度应正确计算。"""
    engine.start_practice_mode(shuffle=False)
    engine.current_index = 4  # 第 5 题
    progress = engine.get_progress()
    assert progress['current'] == 5
    assert progress['total'] == 10
    assert progress['percentage'] == 50.0


def test_get_progress_empty_queue():
    """空 queue 时 percentage 应为 0（不除零）。"""
    eng = QuizEngine([])
    eng.start_practice_mode(shuffle=False)
    progress = eng.get_progress()
    assert progress['total'] == 0
    assert progress['percentage'] == 0


def test_get_progress_includes_stats(engine):
    """progress 应包含 stats。"""
    engine.start_practice_mode(shuffle=False)
    engine.submit_answer('A')
    progress = engine.get_progress()
    assert progress['stats']['total'] == 1
    assert progress['stats']['correct'] == 1


# ---------- get_wrong_answers 测试 ----------

def test_get_wrong_answers_empty(engine):
    """无作答时错题为空。"""
    engine.start_practice_mode(shuffle=False)
    assert engine.get_wrong_answers() == []


def test_get_wrong_answers_all_correct(engine):
    """全对时错题为空。"""
    engine.start_practice_mode(shuffle=False)
    engine.submit_answer('A')  # 第 1 题答案 A
    engine.next_question()
    engine.submit_answer('A')  # 第 2 题答案 A
    assert engine.get_wrong_answers() == []


def test_get_wrong_answers_returns_wrong(engine):
    """应返回答错的题目。"""
    engine.start_practice_mode(shuffle=False)
    engine.submit_answer('B')  # 第 1 题答错
    wrong = engine.get_wrong_answers()
    assert len(wrong) == 1
    assert wrong[0]['number'] == 1


def test_get_wrong_answers_uses_queue_index(engine):
    """get_wrong_answers 应通过 queue_index 反查，而非依赖 current_index。

    模拟跳跃答题：答第 1 题 → 跳到第 5 题答错 → 错题应返回第 5 题。
    """
    engine.start_practice_mode(shuffle=False)
    # 答第 1 题（正确）
    engine.submit_answer('A')
    # 跳到第 5 题
    engine.current_index = 4
    # 答错
    engine.submit_answer('B')
    wrong = engine.get_wrong_answers()
    assert len(wrong) == 1
    assert wrong[0]['number'] == 5  # queue_index=4 → 第 5 题


def test_get_wrong_answers_invalid_index_skipped(engine):
    """queue_index 越界时应跳过，不报错。"""
    engine.start_practice_mode(shuffle=False)
    # 手动注入一条 queue_index 越界的记录
    engine.answers_record.append({
        'queue_index': 999,
        'is_correct': False,
        'question_number': 999,
    })
    # 不应抛异常
    wrong = engine.get_wrong_answers()
    assert len(wrong) == 0  # 越界记录被跳过


def test_get_wrong_answers_missing_queue_index(engine):
    """queue_index 缺失时应跳过。"""
    engine.start_practice_mode(shuffle=False)
    engine.answers_record.append({
        'is_correct': False,
        # 无 queue_index 字段
    })
    wrong = engine.get_wrong_answers()
    assert len(wrong) == 0


# ---------- record_exam_answer 测试 ----------

def test_record_exam_answer_does_not_advance(engine):
    """record_exam_answer 不应推进 current_index。"""
    engine.start_exam_mode(question_count=10, shuffle=False)
    assert engine.current_index == 0
    engine.record_exam_answer(5, 'A')
    assert engine.current_index == 0  # 未推进


def test_record_exam_answer_out_of_bounds(engine):
    """queue_index 越界应返回 None。"""
    engine.start_exam_mode(question_count=10, shuffle=False)
    assert engine.record_exam_answer(999, 'A') is None
    assert engine.record_exam_answer(-1, 'A') is None


def test_record_exam_answer_updates_stats(engine):
    """record_exam_answer 应更新 stats。"""
    engine.start_exam_mode(question_count=10, shuffle=False)
    engine.record_exam_answer(0, 'A')  # 正确
    engine.record_exam_answer(1, 'B')  # 错误
    assert engine.stats['total'] == 2
    assert engine.stats['correct'] == 1
    assert engine.stats['wrong'] == 1


def test_record_exam_answer_multi_record_same_question(engine):
    """同一题多次记录应都生效（考试模式跳跃答题场景）。

    注意：当前实现会重复统计，这是已知行为，测试用于文档化。
    """
    engine.start_exam_mode(question_count=10, shuffle=False)
    engine.record_exam_answer(0, 'B')  # 第一次答错
    engine.record_exam_answer(0, 'A')  # 第二次答对（改答案）
    # 当前实现会统计两次（未去重）
    assert engine.stats['total'] == 2
    assert engine.stats['correct'] == 1
    assert engine.stats['wrong'] == 1


def test_record_exam_answer_multi_choice(engine):
    """考试模式多选题判定。"""
    engine.start_exam_mode(question_count=10, shuffle=False)
    # 第 3 题是多选 ABC
    result = engine.record_exam_answer(2, 'CAB')
    assert result is not None
    assert result['is_correct'] is True


def test_record_exam_answer_result_fields(engine):
    """record_exam_answer 返回结果应包含完整字段。"""
    engine.start_exam_mode(question_count=10, shuffle=False)
    result = engine.record_exam_answer(0, 'A')
    assert 'queue_index' in result
    assert 'question_number' in result
    assert 'selected' in result
    assert 'correct_answer' in result
    assert 'is_correct' in result


# ---------- get_exam_report 测试 ----------

def test_get_exam_report_not_in_exam_mode(engine):
    """未启动考试模式时返回 None。"""
    assert engine.get_exam_report() is None


def test_get_exam_report_practice_mode(engine):
    """练习模式下返回 None（exam_start_time 为 None）。"""
    engine.start_practice_mode(shuffle=False)
    assert engine.get_exam_report() is None


def test_get_exam_report_accuracy(engine):
    """考试报告应正确计算正确率。"""
    engine.start_exam_mode(question_count=10, shuffle=False)
    engine.record_exam_answer(0, 'A')  # 对
    engine.record_exam_answer(1, 'A')  # 对
    engine.record_exam_answer(2, 'D')  # 错（第 3 题答案 ABC）
    engine.record_exam_answer(3, 'B')  # 错（第 4 题答案 A）

    report = engine.get_exam_report()
    assert report is not None
    assert report['total_questions'] == 10
    assert report['correct'] == 2
    assert report['wrong'] == 2
    assert report['accuracy'] == 50.0


def test_get_exam_report_includes_wrong(engine):
    """考试报告应包含错题列表。"""
    engine.start_exam_mode(question_count=10, shuffle=False)
    engine.record_exam_answer(0, 'B')  # 错
    report = engine.get_exam_report()
    assert 'wrong_questions' in report
    assert len(report['wrong_questions']) == 1
    assert report['wrong_questions'][0]['number'] == 1


def test_get_exam_report_zero_division(engine):
    """无作答时正确率应为 0（不除零）。"""
    engine.start_exam_mode(question_count=10, shuffle=False)
    report = engine.get_exam_report()
    assert report is not None
    assert report['accuracy'] == 0
    assert report['correct'] == 0
    assert report['wrong'] == 0


def test_get_exam_report_time_format(engine):
    """考试报告应包含用时字符串。"""
    engine.start_exam_mode(question_count=10, shuffle=False)
    report = engine.get_exam_report()
    assert 'time_used' in report
    assert isinstance(report['time_used'], str)
    assert '分' in report['time_used']


# ---------- get_review_questions 测试 ----------

def test_get_review_questions_returns_all(engine, sample_questions):
    """背题模式应返回全部题目。"""
    engine.start_practice_mode(shuffle=False)
    review = engine.get_review_questions()
    assert len(review) == 10


def test_get_review_questions_returns_copy(engine, sample_questions):
    """get_review_questions 应返回副本，修改不影响原数据。"""
    review = engine.get_review_questions()
    review.clear()
    assert len(engine.all_questions) == 10  # 原数据未受影响


def test_get_review_questions_independent_of_mode(engine):
    """背题模式列表与当前练习/考试模式无关。"""
    engine.start_exam_mode(question_count=3, shuffle=False)
    review = engine.get_review_questions()
    assert len(review) == 10  # 返回全部，不是考试子集
