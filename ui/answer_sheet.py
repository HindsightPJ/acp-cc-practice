"""F 方案网格体右列组件：答题卡（发车时刻表）+ 统计列。

AnswerSheet：一行一题的 dep 行列表（QSS depRow 语义类，state now/done/miss），
点击行发出 row_clicked 信号供宿主跳题。
StatColumn：statBlock 块列（k 标签 + 大号 v 数字 + 单位），展示真实统计。

视觉全部由 theme.py QSS 驱动（QSS 单一取色源），本模块零散写颜色。
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .theme import repolish


class _DepRow(QFrame):
    """单行发车记录：题号 + 状态字 + 右侧符号。

    显示号（原题号）与点击语义（队列索引）解耦：乱序队列中两者不同，
    显示号经 set_no 由宿主同步，点击固定发出 queue_index。
    """

    # 状态文案映射：(状态字, 符号)；缺省 = 待答
    _TEXT = {"done": ("已答", "✓"), "now": ("进行中", "→"), "miss": ("答错", "✗")}

    clicked = Signal(int)  # 发出自身队列索引（0-based）

    def __init__(self, queue_index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.queue_index = queue_index
        self._state = ""
        self.setProperty("depRow", True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        h = QHBoxLayout(self)
        h.setContentsMargins(20, 9, 20, 9)
        h.setSpacing(10)

        self.lbl_no = QLabel(str(queue_index + 1))
        self.lbl_no.setProperty("depN", True)
        self.lbl_st = QLabel("待答")
        self.lbl_st.setProperty("depSt", True)
        self.lbl_sym = QLabel("·")
        self.lbl_sym.setProperty("depSt", True)

        h.addWidget(self.lbl_no)
        h.addWidget(self.lbl_st)
        h.addStretch(1)
        h.addWidget(self.lbl_sym)

    def set_no(self, no: int) -> None:
        """更新显示号（原题号，与题区大号一致）。"""
        self.lbl_no.setText(str(no))

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt 命名
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.queue_index)
        super().mousePressEvent(event)

    def set_state(self, state: str) -> None:
        """state ∈ ""(待答)/done/now/miss；切换 QSS 属性 + 文案并 repolish。

        状态未变化时短路：翻题会对整张答题卡逐行 set_state，868 题全库
        队列下每次导航约 3500 次 setProperty + repolish（递归 unpolish/polish
        整棵子树），而未变化的行占 99% 以上。
        """
        if state == self._state:
            return
        self._state = state
        text, sym = self._TEXT.get(state, ("待答", "·"))
        if state:
            self.setProperty("state", state)
        else:
            self.setProperty("state", None)
        self.lbl_st.setText(text)
        self.lbl_sym.setText(sym)
        repolish(self)


class AnswerSheet(QFrame):
    """答题卡 = 发车时刻表（qcol 右邻列）。

    build_rows(total) 按队列重建行；update_no/update_row 增量更新：
    题目总数不变时用增量更新避免整列重建。
    """

    row_clicked = Signal(int)  # 队列索引（0-based）

    def __init__(self, title: str = "答题卡 · PROGRESS", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("acol")

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        head = QLabel(title)
        head.setObjectName("acolHead")
        v.addWidget(head)

        # dep 行容器放滚动区：题库 50~200 题不撑爆右列
        self._rows_host = QWidget()
        self._rows_host.setObjectName("acolRows")
        self._rows_layout = QVBoxLayout(self._rows_host)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(0)
        self._rows_layout.addStretch(1)  # 常驻尾弹簧：行少时顶部对齐

        scroll = QScrollArea()
        scroll.setWidget(self._rows_host)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        v.addWidget(scroll, 1)

        self._rows: list[_DepRow] = []

    # ------------------------------------------------------------ 数据
    def build_rows(self, total: int) -> None:
        """按队列总题数重建全部 dep 行（开考/重置时调用）。"""
        for row in self._rows:
            self._rows_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()
        for i in range(total):
            row = _DepRow(i, self._rows_host)
            row.clicked.connect(self.row_clicked)
            # 插到尾弹簧之前，保持顶部对齐
            self._rows_layout.insertWidget(self._rows_layout.count() - 1, row)
            self._rows.append(row)

    def update_no(self, index: int, no: int) -> None:
        """同步行显示号为原题号（乱序队列中与队列序号不同）。"""
        if 0 <= index < len(self._rows):
            self._rows[index].set_no(no)

    def update_row(self, index: int, state: str) -> None:
        """增量更新单行状态（state ∈ ""/done/now/miss）。"""
        if 0 <= index < len(self._rows):
            self._rows[index].set_state(state)


class StatColumn(QFrame):
    """统计列（最右列，<900px 由宿主隐藏）：k 标签 + 大号数字 + 单位。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("scol")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 16, 20, 16)
        self._layout.setSpacing(0)
        self._layout.addStretch(1)
        self._blocks: list[tuple[QLabel, QLabel, QLabel]] = []

    def set_stats(self, items: list[tuple[str, str, str]]) -> None:
        """全量刷新统计块：(标签, 数值, 单位) 列表；数量以首次为准。"""
        # 块数量不足时补建（QSS statBlock 驱动样式；单位走 statUnit 16px 类）
        while len(self._blocks) < len(items):
            block = QFrame()
            block.setProperty("statBlock", True)
            bv = QVBoxLayout(block)
            bv.setContentsMargins(0, 8, 0, 14)
            bv.setSpacing(2)
            k = QLabel()
            k.setProperty("statK", True)
            vrow = QHBoxLayout()
            vrow.setSpacing(2)
            v = QLabel()
            v.setProperty("statV", True)
            unit = QLabel()
            unit.setProperty("statUnit", True)
            vrow.addWidget(v)
            vrow.addWidget(unit, 0, Qt.AlignmentFlag.AlignBottom)
            vrow.addStretch(1)
            bv.addWidget(k)
            bv.addLayout(vrow)
            self._layout.insertWidget(self._layout.count() - 1, block)
            self._blocks.append((k, v, unit))

        for i, (k_text, v_text, unit_text) in enumerate(items):
            k_lbl, v_lbl, unit_lbl = self._blocks[i]
            k_lbl.setText(k_text)
            v_lbl.setText(v_text)
            unit_lbl.setText(unit_text)
            unit_lbl.setVisible(bool(unit_text))

    def update_value(self, index: int, text: str) -> None:
        """更新指定统计块的数值文本（倒计时秒级刷新用）。

        存在的理由：调用方（ExamPanel.update_timer_display）此前直接解包
        _blocks 私有结构改标签——块顺序一调整即静默刷错位置，且私有访问
        使封装契约失效。
        """
        if 0 <= index < len(self._blocks):
            self._blocks[index][1].setText(text)
