"""考试视图组件（F 方案网格体）：题区 + 题号导航网格 + 计时统计列 + 动作条。

布局（tkinter ExamPanel 重写为 F 语言）：
- qcol 题区：QuestionDetailCard（无解析块，考试不反馈对错）
- acol 题号网格：5 列 examNav 按钮矩阵（四态：未答/已答/标记/当前），点击跳题
- scol 统计列：剩余时间（大号 mono）+ 已答 + 标记数
- actionsBar：上一题 / 标记本题 / 下一题 / 交卷（go 蓝底）

考试语义：Enter 无提交动作（交卷仅按钮触发，防误交卷）；
选项可反复修改；业务全部委托 ExamSession + QuizEngine。
"""

from typing import Callable

from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .exam_session import ExamSession
from .practice_panel import SCOL_MIN_WIDTH, _make_action_button
from .question_detail_card import QuestionDetailCard, type_label
from .answer_sheet import StatColumn
from .theme import repolish
from quiz_engine import QuizEngine

_NAV_COLS = 5
_STRETCH_NAV, _STRETCH_MARK, _STRETCH_NEXT, _STRETCH_SUBMIT = 10, 10, 10, 14


class ExamPanel(QFrame):
    """考试网格体视图。"""

    def __init__(
        self,
        engine: QuizEngine,
        exam_session: ExamSession,
        on_prev: Callable[[], None] | None = None,
        on_next: Callable[[], None] | None = None,
        on_submit: Callable[[], None] | None = None,  # 交卷（按钮触发）
        on_mark: Callable[[], None] | None = None,  # 标记当前题
        on_jump: Callable[[int], None] | None = None,  # 跳到队列索引
        on_select_option: Callable[[str], None] | None = None,  # 选项切换
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.engine = engine
        self.exam_session = exam_session
        self._on_prev = on_prev
        self._on_next = on_next
        self._on_submit = on_submit
        self._on_mark = on_mark
        self._on_jump = on_jump
        self._on_select_option = on_select_option
        self._nav_buttons: list[QPushButton] = []
        self._last_current_index = -1
        self._time_text = "--:--"  # 计时缓存：stats 列重建时不闪占位符

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # ── grid-body 三列 ──
        body = QFrame()
        h = QHBoxLayout(body)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        qcol = QFrame()
        qcol.setObjectName("qcol")
        qv = QVBoxLayout(qcol)
        qv.setContentsMargins(30, 22, 30, 22)
        self.detail_card = QuestionDetailCard(
            on_option_click=self._handle_option_click, answer_placeholder=""
        )
        qv.addWidget(self.detail_card)
        h.addWidget(qcol, 165)

        # acol 题号网格（5 列 examNav，QScrollArea 防长队列撑爆）
        acol = QFrame()
        acol.setObjectName("acol")
        av = QVBoxLayout(acol)
        av.setContentsMargins(0, 0, 0, 0)
        av.setSpacing(0)
        head = QLabel("题号导航 · NAV")
        head.setObjectName("acolHead")
        av.addWidget(head)

        self._nav_host = QWidget()
        self._nav_grid = QGridLayout(self._nav_host)
        self._nav_grid.setContentsMargins(12, 12, 12, 12)
        self._nav_grid.setSpacing(6)

        scroll = QScrollArea()
        scroll.setWidget(self._nav_host)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        av.addWidget(scroll, 1)
        h.addWidget(acol, 100)

        self.stats_col = StatColumn()
        self.stats_col.setFixedWidth(190)
        h.addWidget(self.stats_col)

        v.addWidget(body, 1)

        # ── actionsBar：上一题 / 标记 / 下一题 / 交卷 ──
        bar = QFrame()
        bar.setObjectName("actionsBar")
        bh = QHBoxLayout(bar)
        bh.setContentsMargins(0, 0, 0, 0)
        bh.setSpacing(0)

        prev_btn = _make_action_button("← 上一题", "←")
        if on_prev is not None:
            prev_btn.clicked.connect(on_prev)
        bh.addWidget(prev_btn, _STRETCH_NAV)

        self.mark_btn = _make_action_button("标记本题", "★")
        if on_mark is not None:
            self.mark_btn.clicked.connect(on_mark)
        bh.addWidget(self.mark_btn, _STRETCH_MARK)

        next_btn = _make_action_button("下一题 →", "→")
        if on_next is not None:
            next_btn.clicked.connect(on_next)
        bh.addWidget(next_btn, _STRETCH_NEXT)

        self.submit_btn = _make_action_button("交卷", "GO", go=True)
        if on_submit is not None:
            self.submit_btn.clicked.connect(on_submit)
        bh.addWidget(self.submit_btn, _STRETCH_SUBMIT)

        v.addWidget(bar)

    # -------------------------------------------------------------- 导航网格
    def build_nav_buttons(self, total: int) -> None:
        """按队列总题数重建题号网格。"""
        for btn in self._nav_buttons:
            self._nav_grid.removeWidget(btn)
            btn.deleteLater()
        self._nav_buttons.clear()
        for i in range(total):
            btn = QPushButton(str(i + 1))
            btn.setProperty("examNav", True)
            btn.clicked.connect(self._make_jump(i))
            self._nav_grid.addWidget(btn, i // _NAV_COLS, i % _NAV_COLS)
            self._nav_buttons.append(btn)

    def _make_jump(self, index: int) -> Callable[[], None]:
        def handler() -> None:
            if self._on_jump is not None:
                self._on_jump(index)

        return handler

    def _apply_nav_style(self, i: int) -> None:
        """四态样式：当前 > 标记 > 已答 > 未答（examNav QSS 属性驱动）。"""
        if not (0 <= i < len(self._nav_buttons)):
            return
        btn = self._nav_buttons[i]
        current = self.engine.get_current_index()
        if i == current:
            state, text = "current", str(i + 1)
        elif self.exam_session.is_marked(i):
            state, text = "marked", f"★{i + 1}"
        elif self.exam_session.has_answer(i):
            state, text = "answered", str(i + 1)
        else:
            state, text = "", str(i + 1)
        btn.setProperty("state", state if state else None)
        btn.setText(text)
        repolish(btn)

    def update_nav_button(self, idx: int) -> None:
        """增量更新单个题号按钮（标记切换时调用）。"""
        self._apply_nav_style(idx)

    # -------------------------------------------------------------- 渲染
    def load_question(self) -> None:
        """加载当前题目、恢复已选状态、同步导航网格与统计列。"""
        question = self.engine.get_current_question()
        if question is None:
            return

        current = self.engine.get_current_index()
        total = self.engine.queue_length()
        self.detail_card.show_question(
            question,
            meta_lines=(type_label(question.type), f"QUEUE {current + 1:02d}/{total:02d}"),
        )

        # 选项重置后恢复已选
        answered = self.exam_session.get_current_selected()
        for i, card in enumerate(self.detail_card.option_cards):
            card.set_selected(chr(ord("A") + i) in answered)

        # 增量刷新导航网格：旧 current + 新 current（长队列防全量抖动）
        if 0 <= self._last_current_index < len(self._nav_buttons) and (
            self._last_current_index != current
        ):
            self._apply_nav_style(self._last_current_index)
        self._apply_nav_style(current)
        self._last_current_index = current

        self._update_stats_col()

    def sync_option_selection(self, selected: str) -> None:
        """选项切换后同步行选中态 + 导航网格（已答态变化）。"""
        for i, card in enumerate(self.detail_card.option_cards):
            card.set_selected(chr(ord("A") + i) in selected)
        self._apply_nav_style(self.engine.get_current_index())
        self._update_stats_col()

    def _update_stats_col(self) -> None:
        """统计列：剩余时间（缓存值）+ 已答 + 标记数。"""
        total = self.engine.queue_length()
        answered = sum(1 for i in range(total) if self.exam_session.has_answer(i))
        marked = sum(1 for i in range(total) if self.exam_session.is_marked(i))
        self.stats_col.set_stats(
            [
                ("剩余时间", self._time_text, ""),
                ("已答", f"{answered}/{total}", ""),
                ("标记", str(marked), "题"),
            ]
        )

    def update_timer_display(self, time_remaining: int, _exam_total_seconds: int) -> None:
        """刷新倒计时（engine 显式接口计算，避免 tick 漂移）。"""
        minutes, seconds = divmod(max(0, time_remaining), 60)
        self._time_text = f"{minutes:02d}:{seconds:02d}"
        if self.stats_col._blocks:
            _k, v_lbl, _u = self.stats_col._blocks[0]
            v_lbl.setText(self._time_text)

    def _handle_option_click(self, letter: str) -> None:
        if self._on_select_option is not None:
            self._on_select_option(letter)

    # -------------------------------------------------------------- 自适应
    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 - Qt 命名
        """窗口 <900px 隐藏统计列（与练习页同策略）。"""
        self.stats_col.setVisible(self.width() >= SCOL_MIN_WIDTH)
        super().resizeEvent(event)
