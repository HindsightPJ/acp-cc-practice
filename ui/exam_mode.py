"""考试模式页：设置视图（题数/时长/历史）⇄ 考试网格体（ExamPanel）编排。

tkinter 版重写。本类只负责编排：开考、计时循环（QTimer 1s + engine 显式
接口防漂移）、交卷评分、历史保存、报告展示。视图渲染委托 ExamPanel。

考试语义（沿袭 tkinter 版）：
- Enter 无提交动作（交卷仅按钮触发，防误交卷）
- 选项可反复修改；考试进度不做持久化（中途退出即放弃本场考试）
"""

from datetime import datetime
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app_state import AppState
from models import Question
from quiz_engine import QuizEngine
from .base_mode import BaseModePage
from .exam_panel import ExamPanel
from .exam_session import ExamSession

# 计时 tick 间隔（原 ui/constants.py TIMER_TICK_MS，就近内联）
TIMER_TICK_MS = 1000

_COUNT_OPTIONS = ("50", "100", "150", "200")
_DURATION_OPTIONS = ("30", "60", "90", "120")
_HISTORY_COLUMNS = ("日期", "题数", "正确", "错误", "正确率", "用时")


class ExamMode(BaseModePage):
    """考试模式编排层。"""

    def __init__(
        self,
        questions: list[Question],
        app_state: AppState,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(app_state, parent)
        self.questions = questions
        self.engine: QuizEngine | None = None
        self.exam_session: ExamSession | None = None
        self.panel: ExamPanel | None = None
        self.timer_running = False
        self.exam_total_seconds = 0
        self.time_remaining = 0

        # 单发计时器（1s tick，running 标志控制），窗口销毁随父控件释放
        self._timer = QTimer(self)
        self._timer.setInterval(TIMER_TICK_MS)
        self._timer.timeout.connect(self._on_timer_tick)

        self._build_ui()

    # -------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self.stack = QStackedWidget()
        v.addWidget(self.stack)
        self.stack.addWidget(self._build_settings_view())
        # 索引 1 占位：开考时创建 ExamPanel 加入

    def _build_settings_view(self) -> QFrame:
        """设置视图：F 排版（无卡片）——标题 + 参数行 + 历史表。"""
        page = QFrame()
        v = QVBoxLayout(page)
        v.setContentsMargins(30, 26, 30, 22)
        v.setSpacing(16)

        title = QLabel("模拟考试")
        title.setObjectName("qBig")
        v.addWidget(title)

        sub = QLabel("EXAM · 从题库随机抽题组卷，交卷后即时评分")
        sub.setObjectName("qMeta")
        v.addWidget(sub)

        # 参数行：题数 + 时长 + 开始按钮
        row = QFrame()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 4, 0, 0)
        h.setSpacing(10)

        h.addWidget(QLabel("题目数量"))
        self.count_combo = QComboBox()
        self.count_combo.addItems(_COUNT_OPTIONS)
        h.addWidget(self.count_combo)
        h.addSpacing(16)
        h.addWidget(QLabel("考试时长(分钟)"))
        self.duration_combo = QComboBox()
        self.duration_combo.addItems(_DURATION_OPTIONS)
        h.addWidget(self.duration_combo)
        h.addStretch(1)

        self.start_btn = QPushButton("开始考试")
        self.start_btn.setObjectName("goBtn")
        self.start_btn.clicked.connect(self.start_exam)
        h.addWidget(self.start_btn)
        v.addWidget(row)

        # 历史表（P0-6 沿袭：最近 20 条，最新在上）
        hist_head = QLabel("最近考试历史 · HISTORY")
        hist_head.setObjectName("acolHead")
        v.addWidget(hist_head)

        self.history_table = QTableWidget(0, len(_HISTORY_COLUMNS))
        self.history_table.setHorizontalHeaderLabels(_HISTORY_COLUMNS)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history_table.horizontalHeader().setStretchLastSection(True)
        v.addWidget(self.history_table, 1)

        self._refresh_history()
        return page

    def _refresh_history(self) -> None:
        """刷新考试历史表（get_exam_history 按时间正序，倒序展示）。"""
        history = list(reversed(self.app_state.get_exam_history()))
        self.history_table.setRowCount(len(history))
        for r, entry in enumerate(history):
            acc = entry.get("accuracy", 0)
            try:
                acc_text = f"{float(acc):.1f}%"
            except (TypeError, ValueError):
                acc_text = "—"
            values = (
                str(entry.get("date", "—")),
                str(entry.get("total_questions", "—")),
                str(entry.get("correct", "—")),
                str(entry.get("wrong", "—")),
                acc_text,
                str(entry.get("time_used", "—")),
            )
            for c, text in enumerate(values):
                self.history_table.setItem(r, c, QTableWidgetItem(text))

    # -------------------------------------------------------------- 开考
    def start_exam(self) -> None:
        """开考：销毁旧 panel（防重复开考泄漏）→ 建引擎/会话/视图 → 计时。

        组卷走 AppState 持久化卡组（draw_exam_questions）：每次考试从
        整库洗牌牌堆顺次抽题，耗尽重洗，保证周期内全库覆盖。
        """
        self._timer.stop()
        self.timer_running = False
        if self.panel is not None:
            self.panel.deleteLater()
            self.panel = None

        try:
            question_count = int(self.count_combo.currentText())
            duration = int(self.duration_combo.currentText())
        except ValueError:
            QMessageBox.critical(self, "错误", "请输入有效的数值！")
            return

        # 卡组抽题 → 按题号组队列（队列顺序即卡组顺序，不再二次洗牌）
        by_number = {q.number: q for q in self.questions}
        drawn = self.app_state.draw_exam_questions(question_count, list(by_number))
        self.engine = QuizEngine([by_number[n] for n in drawn])
        self.engine.start_exam_mode(question_count=len(drawn), shuffle=False)
        self.exam_session = ExamSession(self.engine)
        if not self.app_state.save_safe():
            QMessageBox.warning(
                self, "保存失败", "考试卡组进度保存失败，请检查磁盘空间或文件权限。"
            )

        self.exam_total_seconds = duration * 60
        self.time_remaining = self.exam_total_seconds

        self.panel = ExamPanel(
            self.engine,
            self.exam_session,
            on_prev=self._exam_prev_question,
            on_next=self._exam_next_question,
            on_submit=self.submit_exam,
            on_mark=self._toggle_mark_current,
            on_jump=self._jump_to_question,
            on_select_option=self._select_option_by_letter,
        )
        self.panel.build_nav_buttons(self.engine.queue_length())
        self.stack.addWidget(self.panel)
        self.stack.setCurrentWidget(self.panel)
        self.panel.load_question()

        self.timer_running = True
        self._timer.start()
        self.panel.update_timer_display(self.time_remaining, self.exam_total_seconds)
        self.state_changed.emit()

    # -------------------------------------------------------------- 编排
    def _on_timer_tick(self) -> None:
        """1s tick：engine 显式接口算剩余，防 after 累积漂移；到点自动交卷。"""
        if not self.timer_running:
            return
        if self.engine is not None:
            elapsed = self.engine.get_exam_elapsed_seconds()
            if elapsed is not None:
                self.time_remaining = max(0, self.exam_total_seconds - elapsed)

        if self.time_remaining <= 0:
            self.timer_running = False
            self._timer.stop()
            QMessageBox.warning(self, "时间到", "考试时间已到，将自动交卷！")
            self.submit_exam(force=True)
            return

        if self.panel is not None:
            self.panel.update_timer_display(self.time_remaining, self.exam_total_seconds)

    def _select_option_by_letter(self, letter: str) -> None:
        """选项选择编排：更新 session + 同步视图。"""
        if self.engine is None or self.exam_session is None or self.panel is None:
            return
        selected = self.exam_session.select_option(letter)
        if selected is None:
            return
        self.panel.sync_option_selection(selected)
        self.state_changed.emit()

    def _exam_next_question(self) -> None:
        if self.engine is None or self.panel is None:
            return
        if self.engine.has_next():
            self.engine.next_question()
            self.panel.load_question()
            self.state_changed.emit()
        else:
            QMessageBox.information(self, "提示", "已经是最后一题了！")

    def _exam_prev_question(self) -> None:
        if self.engine is None or self.panel is None:
            return
        if self.engine.has_prev():
            self.engine.prev_question()
            self.panel.load_question()
            self.state_changed.emit()
        else:
            QMessageBox.information(self, "提示", "已经是第一题了！")

    def _jump_to_question(self, idx: int) -> None:
        if self.engine is None or self.panel is None:
            return
        if 0 <= idx < self.engine.queue_length():
            self.engine.set_current_index(idx)
            self.panel.load_question()
            self.state_changed.emit()

    def _toggle_mark_current(self) -> None:
        if self.engine is None or self.exam_session is None or self.panel is None:
            return
        self.exam_session.toggle_mark()
        self.panel.update_nav_button(self.engine.get_current_index())
        self.panel.sync_option_selection(self.exam_session.get_current_selected())
        self.state_changed.emit()

    # -------------------------------------------------------------- 交卷
    def submit_exam(self, force: bool = False) -> None:
        """交卷：确认（附未答/标记数）→ 记录 → 评分 → 历史 + 报告 → 重置。"""
        if not force:
            unanswered = marked = 0
            if self.engine is not None and self.exam_session is not None:
                total = self.engine.queue_length()
                unanswered = sum(1 for i in range(total) if not self.exam_session.has_answer(i))
                marked = sum(1 for i in range(total) if self.exam_session.is_marked(i))
            detail = ""
            if unanswered or marked:
                parts = []
                if unanswered:
                    parts.append(f"未答 {unanswered} 题")
                if marked:
                    parts.append(f"已标记 {marked} 题")
                detail = "\n\n" + "、".join(parts) + "。"
            answer = QMessageBox.question(
                self,
                "确认交卷",
                f"确定要交卷吗？\n\n提交后将无法修改答案。{detail}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        self._timer.stop()
        self.timer_running = False

        if self.engine is None or self.exam_session is None:
            return

        self.exam_session.record_all_answers()
        report = self.engine.get_exam_report()
        if report:
            self._save_exam_history(report)
            self._show_exam_report(report)

        # 交卷后重置 UI，允许同实例重新开考
        if self.panel is not None:
            self.panel.deleteLater()
            self.panel = None
        self.stack.setCurrentIndex(0)
        self._refresh_history()

    def _save_exam_history(self, report: dict[str, Any]) -> None:
        """保存考试历史（save_safe 兜底提示，防静默丢数据）。"""
        self.app_state.add_exam_history(
            {
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "total_questions": report["total_questions"],
                "correct": report["correct"],
                "wrong": report["wrong"],
                "accuracy": report["accuracy"],
                "time_used": report["time_used"],
            }
        )
        if not self.app_state.save_safe():
            QMessageBox.warning(self, "保存失败", "考试历史保存失败，请检查磁盘空间或文件权限。")

    def _show_exam_report(self, report: dict[str, Any]) -> None:
        """报告展示：ExamReportDialog（F 语言），含"加入错题本"回调。"""
        from .exam_report_dialog import ExamReportDialog

        ExamReportDialog(self, report, on_add_wrong=self._add_report_wrong).exec()

    def _add_report_wrong(self, report: dict[str, Any]) -> int:
        """把考试错题加入错题本，返回新增数量（去重后）。"""
        added = 0
        for q in report.get("wrong_questions") or []:
            if not self.app_state.is_wrong_question(q.number):
                self.app_state.add_wrong_question(q.number)
                added += 1
        if added and not self.app_state.save_safe():
            QMessageBox.warning(self, "保存失败", "错题本保存失败，请检查磁盘空间或文件权限。")
        self.state_changed.emit()
        return added

    # -------------------------------------------------------------- 主窗口协议
    def on_letter(self, letter: str) -> None:
        """快捷键 A-D → 选项切换（考试可改答案，无 is_answered 限制）。"""
        if self.stack.currentIndex() == 1:
            self._select_option_by_letter(letter)

    def on_submit(self) -> None:
        """考试模式 Enter 无提交语义（交卷仅按钮触发，防误交卷）。"""

    def on_prev(self) -> None:
        if self.stack.currentIndex() == 1:
            self._exam_prev_question()

    def on_next(self) -> None:
        if self.stack.currentIndex() == 1:
            self._exam_next_question()

    def nav_count(self) -> str | None:
        """board-nav 计数：考试中显示已答/总数，否则 None（缺省 '—'）。"""
        if self.engine is not None and self.exam_session is not None and self.panel is not None:
            total = self.engine.queue_length()
            answered = sum(1 for i in range(total) if self.exam_session.has_answer(i))
            return f"{answered}/{total}"
        return None

    def modeline_text(self) -> str | None:
        if self.engine is not None and self.panel is not None:
            minutes, seconds = divmod(self.time_remaining, 60)
            return (
                f"EXAM · 第 {self.engine.get_current_index() + 1}"
                f"/{self.engine.queue_length()} 题 · 剩余 {minutes:02d}:{seconds:02d}"
            )
        return None
