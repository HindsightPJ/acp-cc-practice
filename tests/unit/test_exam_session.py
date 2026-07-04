"""exam_session.py 单元测试。

覆盖考试模式会话状态管理：选项切换、已答记录、标记、交卷前批量写入。
"""
import pytest

from models import Question, Option
from quiz_engine import QuizEngine
from ui.exam_session import ExamSession


# ---------- 辅助函数 ----------

def make_single_question(number: int, answer: str = 'A') -> Question:
    """构造单选题。"""
    return Question(
        number=number,
        content=f'单选题 {number} 内容',
        options=[
            Option('A', '选项 A'),
            Option('B', '选项 B'),
            Option('C', '选项 C'),
            Option('D', '选项 D'),
        ],
        answer=answer,
        type='single',
        explanation=f'解析 {number}',
    )


def make_multi_question(number: int, answer: str = 'ABC') -> Question:
    """构造多选题。"""
    return Question(
        number=number,
        content=f'多选题 {number} 内容',
        options=[
            Option('A', '选项 A'),
            Option('B', '选项 B'),
            Option('C', '选项 C'),
            Option('D', '选项 D'),
        ],
        answer=answer,
        type='multiple',
        explanation=f'解析 {number}',
    )


@pytest.fixture
def questions():
    return [
        make_single_question(1, answer='A'),
        make_single_question(2, answer='B'),
        make_multi_question(3, answer='AC'),
    ]


@pytest.fixture
def session(questions):
    """构建已启动考试模式的 ExamSession 实例。"""
    engine = QuizEngine(questions)
    engine.start_exam_mode(question_count=len(questions), shuffle=False)
    return ExamSession(engine)


# ---------- 基础查询 ----------

def test_get_current_question(session):
    """get_current_question 返回当前题目。"""
    question = session.get_current_question()
    assert question is not None
    assert question.number == 1


def test_get_current_index(session):
    """初始当前索引为 0。"""
    assert session.get_current_index() == 0


def test_get_current_selected_empty(session):
    """未选择时返回空字符串。"""
    assert session.get_current_selected() == ""


def test_is_multiple_choice(session):
    """单选题返回 False，多选题返回 True。"""
    assert session.is_multiple_choice() is False
    session.engine.set_current_index(2)
    assert session.is_multiple_choice() is True


# ---------- 单选选项切换 ----------

def test_single_select_option(session):
    """单选题选择选项后记录排序后的字母串。"""
    selected = session.select_option('A')
    assert selected == 'A'
    assert session.get_current_selected() == 'A'
    assert session.has_answer(0) is True


def test_single_select_option_replace(session):
    """单选题切换选项会替换原选项。"""
    session.select_option('A')
    selected = session.select_option('B')
    assert selected == 'B'
    assert session.get_current_selected() == 'B'


def test_single_select_same_option_twice_clears(session):
    """单选题再次点击同一选项会取消选择。"""
    session.select_option('A')
    selected = session.select_option('A')
    assert selected == ""
    assert session.get_current_selected() == ""
    assert session.has_answer(0) is False


# ---------- 多选选项切换 ----------

def test_multi_select_option_toggle(session):
    """多选题可累计选择多个选项。"""
    session.engine.set_current_index(2)
    session.select_option('A')
    session.select_option('C')
    assert session.get_current_selected() == 'AC'


def test_multi_select_option_deselect(session):
    """多选题再次点击已选选项会取消。"""
    session.engine.set_current_index(2)
    session.select_option('A')
    session.select_option('C')
    session.select_option('A')
    assert session.get_current_selected() == 'C'


# ---------- 边界与异常 ----------

def test_select_option_out_of_range(session):
    """选择不存在的选项返回 None。"""
    assert session.select_option('Z') is None


def test_select_option_no_question():
    """题目队列为空时返回 None。"""
    engine = QuizEngine([])
    engine.start_exam_mode(question_count=0, shuffle=False)
    session = ExamSession(engine)
    assert session.select_option('A') is None


# ---------- 标记 ----------

def test_toggle_mark(session):
    """切换标记状态。"""
    session.toggle_mark()
    assert session.is_marked(0) is True
    session.toggle_mark()
    assert session.is_marked(0) is False


def test_toggle_mark_returns_index(session):
    """toggle_mark 返回当前索引。"""
    session.engine.set_current_index(1)
    assert session.toggle_mark() == 1


# ---------- 交卷前批量写入 ----------

def test_record_all_answers_writes_to_engine(session):
    """record_all_answers 把已选答案写入 QuizEngine。"""
    session.select_option('A')  # 题 1，正确
    session.engine.next_question()
    session.select_option('B')  # 题 2，正确
    session.engine.next_question()
    session.select_option('A')  # 题 3，多选题部分正确

    session.record_all_answers()

    assert session.engine.is_answered(0) is True
    assert session.engine.is_answered(1) is True
    assert session.engine.is_answered(2) is True

    report = session.engine.get_exam_report()
    assert report is not None
    assert report['correct'] == 2
    assert report['wrong'] == 1


def test_record_all_answers_restores_index(session):
    """record_all_answers 执行后恢复原始 current_index。"""
    session.engine.set_current_index(1)
    session.select_option('B')
    session.record_all_answers()
    assert session.engine.get_current_index() == 1
