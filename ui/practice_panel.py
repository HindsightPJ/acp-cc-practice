"""练习视图组件（F 方案网格体，PracticeMode 与 WrongBook 错题练习共用）。

布局（mockup proposal_F_transit.html）：
- grid-body 三列：qcol 题区（QuestionDetailCard）+ acol 答题卡（AnswerSheet
  dep 行，点击跳题）+ scol 统计列（窗口 <900px 时隐藏）
- 底部 actionsBar：重新开始 / 上一题 / 提交答案 / 下一题(go 蓝底)

业务全部委托 PracticeSession（引擎与判题），本类只做渲染与回调转发：
提交完成 → on_submit；切题 → on_navigate；队列完成 → on_finish。
调用方（宿主模式页）负责快照同步与防抖保存。
"""

from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app_state import AppState
from .answer_sheet import AnswerSheet, StatColumn
from .practice_session import PracticeSession
from .question_detail_card import QuestionDetailCard, type_label

# scol 统计列在窗口宽度低于该值时隐藏（TASK_PLAN §6.4 默认决策）
SCOL_MIN_WIDTH = 900
# actionsBar 按钮比例（mockup：上一题 1 / 提交 1 / 下一题 go 1.4，重启 0.7）
_STRETCH_RESTART, _STRETCH_NAV, _STRETCH_SUBMIT, _STRETCH_GO = 7, 10, 10, 14


def _make_action_button(text: str, kbd: str = "", go: bool = False) -> QPushButton:
    """构造动作条按钮：文本 + 等宽键位提示（QSS actBtn/goBtn 语义类）。"""
    btn = QPushButton()
    if go:
        btn.setObjectName("goBtn")
    else:
        btn.setProperty("actBtn", True)
    h = QHBoxLayout(btn)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(8)
    h.addStretch(1)
    lbl = QLabel(text)
    # 按钮自身 :hover/:pressed 只刷按钮背景，文字色由 goBtn/actBtn QSS 兜底
    lbl.setStyleSheet("background: transparent;")
    h.addWidget(lbl)
    if kbd:
        k = QLabel(kbd)
        k.setProperty("kbdHint", True)
        h.addWidget(k)
    h.addStretch(1)
    return btn


class PracticePanel(QFrame):
    """可复用的练习视图（题区 + 答题卡 + 统计列 + 动作条）。"""

    def __init__(
        self,
        session: PracticeSession,
        app_state: AppState,
        on_finish=None,  # Callable[[], None] | None
        on_submit=None,  # Callable[[], None] | None  提交完成后回调（宿主防抖保存）
        on_navigate=None,  # Callable[[], None] | None  切题后回调（宿主防抖保存）
        on_restart=None,  # Callable[[], None] | None  重新开始按钮回调
        show_prev_button: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.session = session
        self.app_state = app_state
        self._on_finish = on_finish
        self._on_submit = on_submit
        self._on_navigate = on_navigate
        self.show_prev_button = show_prev_button

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # ── grid-body 三列 ──
        body = QFrame()
        h = QHBoxLayout(body)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        # qcol 题区列（QSS border-right）
        qcol = QFrame()
        qcol.setObjectName("qcol")
        qv = QVBoxLayout(qcol)
        qv.setContentsMargins(30, 22, 30, 22)
        self.detail_card = QuestionDetailCard(
            on_option_click=self.handle_option_click,
            answer_placeholder="提交答案后查看解析",
        )
        qv.addWidget(self.detail_card)
        h.addWidget(qcol, 165)

        # acol 答题卡列（dep 行，点击跳题）
        self.sheet = AnswerSheet()
        self.sheet.row_clicked.connect(self.jump_to_index)
        h.addWidget(self.sheet, 100)

        # scol 统计列（<900px 隐藏）
        self.stats_col = StatColumn()
        h.addWidget(self.stats_col)
        self.stats_col.setFixedWidth(190)

        v.addWidget(body, 1)

        # ── actionsBar ──
        bar = QFrame()
        bar.setObjectName("actionsBar")
        bh = QHBoxLayout(bar)
        bh.setContentsMargins(0, 0, 0, 0)
        bh.setSpacing(0)

        self.restart_btn = _make_action_button("重新开始", "")
        if on_restart is not None:
            self.restart_btn.clicked.connect(on_restart)
        else:
            self.restart_btn.setEnabled(False)
        bh.addWidget(self.restart_btn, _STRETCH_RESTART)

        if self.show_prev_button:
            self.prev_btn = _make_action_button("← 上一题", "←")
            self.prev_btn.clicked.connect(self.prev_question)
            bh.addWidget(self.prev_btn, _STRETCH_NAV)

        self.submit_btn = _make_action_button("提交答案", "ENTER")
        self.submit_btn.clicked.connect(self.submit_answer)
        bh.addWidget(self.submit_btn, _STRETCH_SUBMIT)

        self.next_btn = _make_action_button("下一题 →", "→", go=True)
        self.next_btn.clicked.connect(self.next_question)
        bh.addWidget(self.next_btn, _STRETCH_GO)

        v.addWidget(bar)

    # -------------------------------------------------------------- 渲染
    def load_current_question(self) -> None:
        """加载当前题目并更新视图；队列耗尽时触发 on_finish。"""
        question = self.session.load_current_question()
        if not question:
            if self._on_finish is not None:
                self._on_finish()
            else:
                QMessageBox.information(self, "提示", "已完成所有题目！")
            return

        current = self.session.engine.get_current_index()
        total = self.session.engine.queue_length()
        self.detail_card.show_question(
            question,
            meta_lines=(type_label(question.type), f"QUEUE {current + 1:02d}/{total:02d}"),
        )
        # 把题型同步进 session：多选题需切换式选择，不同步会被当成单选
        self.session.get_question_type(question)
        self.session.reset_selection()
        self.submit_btn.setEnabled(True)

        self._update_sheet()
        self._update_stats_col()

    def _update_sheet(self) -> None:
        """答题卡全量同步：done（答对）/ miss（答错）/ now（当前）。"""
        engine = self.session.engine
        current = engine.get_current_index()
        correct = engine.get_correct_question_numbers()  # 题号集合（非队列索引）
        total = engine.queue_length()
        for i in range(total):
            if i == current:
                state = "now"
            elif engine.is_answered(i):
                q = engine.get_question_at(i)
                state = "done" if q is not None and q.number in correct else "miss"
            else:
                state = ""
            self.sheet.update_row(i, state)

    def _update_stats_col(self) -> None:
        """统计列：正确率 / 已答 / 错题本（真实数据，无装饰性指标）。"""
        stats = self.session.get_stats()
        accuracy = (stats["correct"] / stats["total"] * 100) if stats["total"] > 0 else 0
        total = self.session.engine.queue_length()
        self.stats_col.set_stats(
            [
                ("正确率", f"{accuracy:.0f}", "%"),
                ("已答", f"{stats['total']}/{total}", ""),
                ("错题本", str(self.app_state.wrong_count()), "题"),
            ]
        )

    # -------------------------------------------------------------- 交互
    def handle_option_click(self, letter: str) -> None:
        """处理选项点击。"""
        question = self.session.engine.get_current_question()
        if question is None:
            return

        options_count = len(question.options)
        self.session.handle_option_click(letter, options_count)

        if self.session.current_question_type == "single":
            for i, card in enumerate(self.detail_card.option_cards):
                card.set_selected(i == ord(letter) - ord("A"))
        else:
            idx = ord(letter) - ord("A")
            self.detail_card.option_cards[idx].set_selected(self.session.is_option_selected(letter))

    def submit_answer(self) -> None:
        """提交答案并更新视图。"""
        if not self.session.selected_answers:
            QMessageBox.warning(self, "提示", "请先选择一个答案！")
            return

        question = self.session.engine.get_current_question()
        if question is None:
            return

        result = self.session.submit_answer()
        if result is None:
            return

        if result["is_correct"]:
            self.detail_card.set_verdict("回答正确", ok=True)
        else:
            self.detail_card.set_verdict(
                f"回答错误，正确答案: {result['correct_answer']}", ok=False
            )

        explanation = question.explanation or "暂无解析"
        if len(explanation) < 5:
            explanation = "暂无详细解析"
        self.detail_card.set_explanation(explanation)
        self.detail_card.set_option_result(question.answer, "".join(self.session.selected_answers))

        self.submit_btn.setEnabled(False)
        if self._on_submit is not None:
            self._on_submit()
        self._update_sheet()
        self._update_stats_col()

    def next_question(self) -> None:
        """下一题；末题已作答再点下一题 = 队列完成，触发 on_finish。"""
        if self.session.has_next():
            self.session.next_question()
            self.load_current_question()
            if self._on_navigate is not None:
                self._on_navigate()
            return
        engine = self.session.engine
        current = engine.get_current_index()
        if engine.queue_length() and engine.is_answered(current):
            # 末题已提交后再点下一题 → 完成流程（宿主统计/错题移除）
            if self._on_finish is not None:
                self._on_finish()
            else:
                QMessageBox.information(self, "提示", "已完成所有题目！")
        else:
            QMessageBox.information(self, "提示", "已经是最后一题了！")

    def prev_question(self) -> None:
        """上一题。"""
        if self.session.has_prev():
            self.session.prev_question()
            self.load_current_question()
            if self._on_navigate is not None:
                self._on_navigate()
        else:
            QMessageBox.information(self, "提示", "已经是第一题了！")

    def jump_to_index(self, index: int) -> None:
        """答题卡点击跳题（AnswerSheet row_clicked）。"""
        engine = self.session.engine
        if 0 <= index < engine.queue_length() and index != engine.get_current_index():
            engine.set_current_index(index)
            self.load_current_question()
            if self._on_navigate is not None:
                self._on_navigate()

    def reset_session(self, shuffle: bool = False) -> None:
        """重置练习会话并重渲染。"""
        self.session.reset_session(shuffle=shuffle)
        self.sheet.build_rows(self.session.engine.queue_length())
        self.load_current_question()

    # -------------------------------------------------------------- 自适应
    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 - Qt 命名
        """窗口 <900px 隐藏统计列（F 方案窄窗折叠策略）。"""
        self.stats_col.setVisible(self.width() >= SCOL_MIN_WIDTH)
        super().resizeEvent(event)

    # -------------------------------------------------------------- 主窗口协议
    def nav_count(self) -> str:
        """board-nav 右侧计数（mockup cnt 形态 12/50）。"""
        engine = self.session.engine
        return f"{engine.get_current_index() + 1}/{engine.queue_length()}"

    def modeline_text(self) -> str:
        """modeline 文案：练习进度 + 本次正确率。"""
        stats = self.session.get_stats()
        accuracy = (stats["correct"] / stats["total"] * 100) if stats["total"] > 0 else 0
        return (
            f"PRACTICE · 第 {self.session.engine.get_current_index() + 1}"
            f"/{self.session.engine.queue_length()} 题 · 本次正确率 {accuracy:.0f}%"
        )
