"""统一的选项行组件（F 方案发牌板行形态）。

四种模式（练习 / 考试 / 背题 / 错题）共用同一个 OptionRow，避免四套样式
逻辑漂移。视觉完全由 theme.py QSS 的 optRow 语义类驱动（QSS 单一取色源），
本组件只负责切换 state 动态属性 + repolish，零散写颜色。

状态机（QSS 属性 state，QFrame[optRow="true"][state=...]）：
- 无属性 = idle（默认行）
- "selected" = 用户选中（IKB 蓝反白）
- "ok"       = 正确答案高亮（字母/标记转蓝）
- "wrong"    = 用户选错（整行转灰）

QSS 边界（P2 工程发现）：祖先带伪类的后代选择器不可用，但祖先**属性**
选择器（QFrame[optRow][state=...] QLabel）实测正常，本组件安全使用。

调用方负责：
1. 实例化时传 letter / on_click；
2. 切题前 reset() 清状态；
3. 用户点击触发 on_click(letter) 后，调用方决定 set_selected(True/False)；
4. 提交答案后调用 set_result(is_correct, is_selected_answer)。
"""

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel

from .theme import repolish

# mark 文案（mockup 语义：选中行反白、正确答案蓝标、未选行灰标）
_MARK_SELECTED = "已选"
_MARK_CORRECT = "✓ 正确答案"  # 背题模式（无作答）高亮正确答案用
_MARK_PICKED_OK = "已选 ✓"  # 多选逐字母判定：选对
_MARK_MISSED_OK = "未选 ✓"  # 多选逐字母判定：漏选
_MARK_WRONG_PICKED = "已选 ✗"  # 多选逐字母判定：错选
_MARK_UNSELECTED = "— 未选"


class OptionRow(QFrame):
    """单行选项：左侧字母 + 中间文本 + 右侧结果标记，整行由 QSS 驱动。"""

    def __init__(
        self,
        letter: str,
        on_click: Callable[[str], None] | None = None,
        parent: QFrame | None = None,
    ) -> None:
        super().__init__(parent)
        self.letter = letter
        self._on_click = on_click

        self.setProperty("optRow", True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        h = QHBoxLayout(self)
        h.setContentsMargins(6, 12, 6, 12)
        h.setSpacing(14)

        self.key_label = QLabel(letter)
        self.key_label.setProperty("optKey", True)
        self.key_label.setMinimumWidth(20)

        self.text_label = QLabel()
        self.text_label.setProperty("optText", True)
        self.text_label.setWordWrap(True)

        self.mark_label = QLabel()
        self.mark_label.setProperty("optMark", True)

        h.addWidget(self.key_label)
        h.addWidget(self.text_label, 1)
        h.addWidget(self.mark_label)

    # ------------------------------------------------------------ 事件
    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt 命名
        if event.button() == Qt.MouseButton.LeftButton and self._on_click is not None:
            self._on_click(self.letter)
        super().mousePressEvent(event)

    # ------------------------------------------------------------ 状态
    def update_text(self, text: str) -> None:
        self.text_label.setText(text)

    def _set_state(self, state: str | None, mark: str) -> None:
        """统一切换 state 属性 + mark 文案并 repolish（QSS 单点驱动）。"""
        if state is None:
            self.setProperty("state", None)
        else:
            self.setProperty("state", state)
        self.mark_label.setText(mark)
        repolish(self)

    def reset(self) -> None:
        """切题时清空所有状态。"""
        self._set_state(None, "")

    def set_selected(self, selected: bool) -> None:
        """用户切换选中态（未提交前）。"""
        self._set_state("selected" if selected else None, _MARK_SELECTED if selected else "")

    def set_result(self, is_correct: bool, is_selected_answer: bool) -> None:
        """提交后标记结果态（四象限，逐字母判定，对齐 mockup proposal_F_transit）。

        Args:
            is_correct: 该字母是否属于正确答案
            is_selected_answer: 该字母是否被用户选中

        四象限文案：
        - (True, True)   → 选对：反白 + 已选 ✓
        - (True, False)  → 漏选：字母转蓝 + 未选 ✓
        - (False, True)  → 错选：仍反白（保留"被点过"视觉）+ 已选 ✗
        - (False, False) → 未选的干扰项：整行灰 + — 未选
        """
        if is_correct and is_selected_answer:
            self._set_state("selected", _MARK_PICKED_OK)
        elif is_correct:
            self._set_state("ok", _MARK_MISSED_OK)
        elif is_selected_answer:
            self._set_state("selected", _MARK_WRONG_PICKED)
        else:
            self._set_state("wrong", _MARK_UNSELECTED)

    def reveal_correct(self) -> None:
        """背题模式：高亮正确答案。"""
        self._set_state("ok", _MARK_CORRECT)
