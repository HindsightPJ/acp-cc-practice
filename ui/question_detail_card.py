"""题目详情卡组件（F 方案 qcol 题区列内容）。

练习 / 背题 / 错题详情三处复用，只负责"题目内容渲染"：
qline 题头（大号题号 + meta 行）→ stem 题干 → opts 选项行 → expBox 解析块。
外壳（模式页网格 / 详情对话框）由调用方组合。

视觉全部由 theme.py QSS 语义类驱动（qline/qBig/qMeta/stem/opts/expBox），
本模块零散写颜色。提交后的判定结果用 verdict 属性驱动（ok=蓝 / wrong=灰，
F 方案仅黑 + IKB 蓝一个强调色，无红绿语义）。
"""

from typing import Callable

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from models import Question
from .option_row import OptionRow
from .theme import repolish

# 题干最多 6 个选项（A-F）——原 ui/constants.py MAX_OPTIONS，就近内联
MAX_OPTIONS = 6

_QUESTION_TYPE_LABELS = {"multiple": "多选题"}


def type_label(question_type: str) -> str:
    """题型文案（"single"/其他 → 单选题）。"""
    return _QUESTION_TYPE_LABELS.get(question_type, "单选题")


class QuestionDetailCard(QFrame):
    """题干 + 选项 + 解析块的组合组件。

    Args:
        on_option_click: 选项点击回调 (letter)；None = 只读（背题/详情场景）
        answer_placeholder: 解析块判定行的占位文案（空串 = 不显示解析块）
    """

    def __init__(
        self,
        on_option_click: Callable[[str], None] | None = None,
        answer_placeholder: str = "",
        parent: QFrame | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_option_click = on_option_click
        self._answer_placeholder = answer_placeholder

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # qline 题头：大号题号 + meta 纵排（4px 视觉锚点 = 下边 1px INK 规则线）
        qline = QFrame()
        qline.setObjectName("qline")
        h = QHBoxLayout(qline)
        h.setContentsMargins(0, 0, 0, 14)
        h.setSpacing(14)
        self.big_no = QLabel()
        self.big_no.setObjectName("qBig")
        self._meta_box = QVBoxLayout()
        self._meta_box.setSpacing(5)
        self._meta_labels = [QLabel() for _ in range(2)]
        for lbl in self._meta_labels:
            lbl.setObjectName("qMeta")
            self._meta_box.addWidget(lbl)
        h.addWidget(self.big_no)
        h.addLayout(self._meta_box)
        h.addStretch(1)
        v.addWidget(qline)

        # 题干
        self.stem = QLabel()
        self.stem.setObjectName("stem")
        self.stem.setWordWrap(True)
        v.addWidget(self.stem)

        # 选项容器（QSS opts 类提供顶部 1px INK 规则线）
        opts = QFrame()
        opts.setObjectName("opts")
        self._opts_layout = QVBoxLayout(opts)
        self._opts_layout.setContentsMargins(0, 0, 0, 0)
        self._opts_layout.setSpacing(0)
        self.option_cards: list[OptionRow] = []
        for idx in range(MAX_OPTIONS):
            row = OptionRow(chr(ord("A") + idx), on_click=self._handle_option_click)
            self._opts_layout.addWidget(row)
            self.option_cards.append(row)
        v.addWidget(opts)

        # 解析块（4px 规则线压顶，默认隐藏）
        self._exp_box = QFrame()
        self._exp_box.setObjectName("expBox")
        ev = QVBoxLayout(self._exp_box)
        ev.setContentsMargins(0, 14, 0, 0)
        ev.setSpacing(8)
        self.exp_result = QLabel()
        self.exp_result.setObjectName("expResult")
        self.exp_text = QLabel()
        self.exp_text.setObjectName("expText")
        self.exp_text.setWordWrap(True)
        ev.addWidget(self.exp_result)
        ev.addWidget(self.exp_text)
        self._exp_box.setVisible(False)
        v.addWidget(self._exp_box)
        v.addStretch(1)

    # ------------------------------------------------------------ 选项事件
    def _handle_option_click(self, letter: str) -> None:
        if self._on_option_click is not None:
            self._on_option_click(letter)

    # ------------------------------------------------------------ 渲染
    def show_question(
        self,
        question: Question,
        meta_lines: tuple[str, ...] = (),
        reveal_answer: bool = False,
    ) -> None:
        """渲染题干与选项；可选同时高亮正确答案与显示解析。

        meta_lines 覆盖题头两行 meta（不足的行隐藏）。
        """
        self.big_no.setText(str(question.number))

        lines = list(meta_lines)
        if not lines:
            lines = [type_label(question.type), f"题号 {question.number}"]
        for i, lbl in enumerate(self._meta_labels):
            if i < len(lines):
                lbl.setText(lines[i])
                # 多选题标签 ACCENT 变色提醒（QSS qType 属性驱动，换题需 repolish）
                is_multi = any(t in lines[i] for t in _QUESTION_TYPE_LABELS.values())
                lbl.setProperty("qType", "multiple" if is_multi else None)
                repolish(lbl)
                lbl.setVisible(True)
            else:
                lbl.setVisible(False)

        self.stem.setText(question.content)

        options_count = len(question.options)
        for i, card in enumerate(self.option_cards):
            if i < options_count:
                card.setVisible(True)
                card.update_text(question.options[i].text)
                card.reset()
            else:
                card.setVisible(False)

        if reveal_answer:
            self.reveal_correct_options(question)
            self.set_verdict(f"正确答案: {question.answer or '未知'}", ok=True)
            self.set_explanation(question.explanation or "暂无解析")
        else:
            self.clear_answer_state()

    def reveal_correct_options(self, question: Question) -> None:
        """高亮正确答案选项，其余选项 reset。仅改选项状态，不动解析块。"""
        correct_answer = question.answer or ""
        for i, card in enumerate(self.option_cards):
            letter = chr(ord("A") + i)
            if letter in correct_answer and i < len(question.options):
                card.reveal_correct()
            else:
                card.reset()

    def set_option_result(self, correct_answer: str, selected: str) -> None:
        """提交后标记选项结果态（全部选项行参与，未选干扰项灰标"— 未选"）。

        Args:
            correct_answer: 正确答案字母串，如 "ABC"
            selected: 用户选中的字母串，如 "AC"
        """
        correct_set = set(correct_answer)
        selected_set = set(selected)
        for i, card in enumerate(self.option_cards):
            letter = chr(ord("A") + i)
            card.set_result(letter in correct_set, letter in selected_set)

    def reset_options(self) -> None:
        """重置所有选项状态为 idle。"""
        for card in self.option_cards:
            card.reset()

    # ------------------------------------------------------------ 解析块
    def set_verdict(self, text: str, ok: bool) -> None:
        """判定行：ok=True 蓝（正确）、False 灰（错误），verdict 属性驱动 QSS。"""
        self._exp_box.setVisible(True)
        self.exp_result.setText(text)
        self.exp_result.setProperty("verdict", "ok" if ok else "wrong")
        repolish(self.exp_result)

    def set_explanation(self, text: str) -> None:
        """更新解析文本（同时显示解析块）。"""
        self._exp_box.setVisible(True)
        self.exp_text.setText(text)

    def clear_answer_state(self) -> None:
        """重置解析块为占位态（无占位文案时整体隐藏），清空解析。"""
        if self._answer_placeholder:
            self._exp_box.setVisible(True)
            self.exp_result.setProperty("verdict", None)
            self.exp_result.setText(self._answer_placeholder)
            self.exp_text.setText("")
            repolish(self.exp_result)
        else:
            self._exp_box.setVisible(False)
            self.exp_text.setText("")
