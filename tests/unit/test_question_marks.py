"""选项行四象限标记 + 题型标签变色测试（P9-4）。

口径（用户定义，多选逐字母判定）：
- 已选 ✓（选对，反白）/ 未选 ✓（漏选，字母转蓝）
- 已选 ✗（错选，反白）/ — 未选（未选干扰项，整行灰）
reveal_correct（背题模式，无作答）仍为 "✓ 正确答案"。

题型标签：meta 行含"多选题"时 qType="multiple"（QSS ACCENT 变色），
单选/背题等其它文案保持默认灰。
"""

import pytest

from models import Question
from ui.option_row import OptionRow
from ui.question_detail_card import QuestionDetailCard

pytestmark = pytest.mark.gui


@pytest.fixture(autouse=True)
def _ensure_qapp(qapp):
    """纯逻辑用例（不触 qtbot）也必须先有 QApplication，QWidget 才能创建。"""
    yield


def _make_row() -> OptionRow:
    row = OptionRow("A")
    row.update_text("选项文本")
    return row


# ---------- OptionRow 四象限 ----------


def test_set_result_picked_ok():
    """选对：反白 + 已选 ✓。"""
    row = _make_row()
    row.set_result(True, True)
    assert row.property("state") == "selected"
    assert row.mark_label.text() == "已选 ✓"


def test_set_result_missed_ok():
    """漏选：字母转蓝 + 未选 ✓。"""
    row = _make_row()
    row.set_result(True, False)
    assert row.property("state") == "ok"
    assert row.mark_label.text() == "未选 ✓"


def test_set_result_wrong_picked():
    """错选：反白 + 已选 ✗。"""
    row = _make_row()
    row.set_result(False, True)
    assert row.property("state") == "selected"
    assert row.mark_label.text() == "已选 ✗"


def test_set_result_unselected_distractor():
    """未选干扰项：整行灰 + — 未选。"""
    row = _make_row()
    row.set_result(False, False)
    assert row.property("state") == "wrong"
    assert row.mark_label.text() == "— 未选"


def test_reveal_correct_keeps_answer_semantics():
    """背题模式无作答，reveal_correct 仍是 ✓ 正确答案。"""
    row = _make_row()
    row.reveal_correct()
    assert row.property("state") == "ok"
    assert row.mark_label.text() == "✓ 正确答案"


# ---------- 详情卡逐字母判定 ----------


def _make_question(q_type: str, answer: str) -> Question:
    from models import Option

    return Question(
        number=8,
        content="题干",
        options=[Option(letter, f"选项 {letter}") for letter in "ABCD"],
        answer=answer,
        type=q_type,
        explanation="解析",
    )


def test_detail_card_set_option_result_multi_per_letter(qtbot):
    """详情卡多选提交：AC 正确、用户选 A → A 已选✓，C 未选✓，B/D 灰。"""
    card = QuestionDetailCard()
    qtbot.addWidget(card)
    card.show_question(_make_question("multiple", "AC"))
    card.set_option_result("AC", "A")
    by_letter = {c.letter: c for c in card.option_cards}
    assert by_letter["A"].mark_label.text() == "已选 ✓"
    assert by_letter["C"].mark_label.text() == "未选 ✓"
    assert by_letter["B"].mark_label.text() == "— 未选"
    assert by_letter["D"].mark_label.text() == "— 未选"


# ---------- 题型标签变色 ----------


def test_detail_card_multi_type_tag_colored(qtbot):
    """多选题 meta 行 qType=multiple（QSS ACCENT 变色），单选不带属性。"""
    card = QuestionDetailCard()
    qtbot.addWidget(card)

    card.show_question(_make_question("multiple", "AC"))
    assert card._meta_labels[0].text() == "多选题"
    assert card._meta_labels[0].property("qType") == "multiple"

    card.show_question(_make_question("single", "A"))
    assert card._meta_labels[0].text() == "单选题"
    assert card._meta_labels[0].property("qType") is None


def test_detail_card_multi_tag_colored_in_custom_meta(qtbot):
    """调用方自定义 meta（如错题本"多选题 · 题号 8"）同样变色。"""
    card = QuestionDetailCard()
    qtbot.addWidget(card)
    card.show_question(_make_question("multiple", "AC"), meta_lines=("错题本", "多选题 · 题号 8"))
    assert card._meta_labels[1].property("qType") == "multiple"
    assert card._meta_labels[0].property("qType") is None
