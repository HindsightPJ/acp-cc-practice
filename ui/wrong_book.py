"""错题本页：列表视图 ⇄ 错题专项练习视图。

tkinter 版重写（原实现为 Toplevel 子窗口练习，PySide6 版收敛为主窗口
页内双视图切换，符合 F 方案"主窗口单舞台"语言）：
- 列表视图：QTableWidget 错题清单（双击 = 详情，P5 接入卡片对话框）
- 练习视图：复用 PracticePanel（错题队列表决于当下错题本快照）

完成流程沿袭 tkinter 版：队列答完后提示统计，询问是否移除本次答对的
错题（移除即"已掌握"），保存后回列表。
"""

from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import (
    QAbstractItemView,
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
from .practice_panel import PracticePanel
from .practice_session import PracticeSession
from .question_detail_card import type_label

_LIST_COLUMNS = ("题号", "题型", "题干摘要")


class WrongBookPage(BaseModePage):
    """错题本页。"""

    _save_failure_message = "错题本保存失败，请检查磁盘空间或文件权限。"

    def __init__(
        self,
        questions: list[Question],
        app_state: AppState,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(app_state, parent)
        self.all_questions = questions
        self._by_number = {q.number: q for q in questions}
        self.practice_engine: QuizEngine | None = None
        self.practice_session: PracticeSession | None = None
        self.panel: PracticePanel | None = None

        self._build_ui()

    # -------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self.stack = QStackedWidget()
        v.addWidget(self.stack)
        self.stack.addWidget(self._build_list_view())

    def _build_list_view(self) -> QFrame:
        """列表视图：头部行（计数 + 动作）+ 错题表。"""
        page = QFrame()
        v = QVBoxLayout(page)
        v.setContentsMargins(30, 26, 30, 22)
        v.setSpacing(16)

        head = QFrame()
        h = QHBoxLayout(head)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(10)

        title_box = QVBoxLayout()
        title_box.setSpacing(5)
        self.count_label = QLabel("错题本")
        self.count_label.setObjectName("qBig")
        sub = QLabel("WRONGBOOK · 双击条目查看详情")
        sub.setObjectName("qMeta")
        title_box.addWidget(self.count_label)
        title_box.addWidget(sub)
        h.addLayout(title_box)
        h.addStretch(1)

        clear_btn = QPushButton("清空错题本")
        clear_btn.setProperty("actBtn", True)
        clear_btn.clicked.connect(self._clear_wrong_book)
        h.addWidget(clear_btn)

        practice_btn = QPushButton("开始错题练习 →")
        practice_btn.setObjectName("goBtn")
        practice_btn.clicked.connect(self.start_practice)
        h.addWidget(practice_btn)
        v.addWidget(head)

        self.table = QTableWidget(0, len(_LIST_COLUMNS))
        self.table.setHorizontalHeaderLabels(_LIST_COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.doubleClicked.connect(self._show_detail)
        v.addWidget(self.table, 1)

        self._refresh_table()
        return page

    def _refresh_table(self) -> None:
        """刷新错题清单（app_state 为唯一数据源）。"""
        wrong_nums = self.app_state.get_wrong_questions()
        self.count_label.setText(f"错题本 · {len(wrong_nums)} 题")
        self.table.setRowCount(len(wrong_nums))
        for r, num in enumerate(wrong_nums):
            q = self._by_number.get(num)
            content = q.content if q is not None else "（题目缺失）"
            values = (
                str(num),
                type_label(q.type) if q is not None else "—",
                content if len(content) <= 60 else content[:60] + "…",
            )
            for c, text in enumerate(values):
                self.table.setItem(r, c, QTableWidgetItem(text))

    # -------------------------------------------------------------- 详情
    def _show_detail(self, index: QModelIndex | int) -> None:
        """查看错题详情：BaseDialog + QuestionDetailCard（F 语言复用）。"""
        row = index.row() if isinstance(index, QModelIndex) else int(index)
        wrong_nums = self.app_state.get_wrong_questions()
        if not (0 <= row < len(wrong_nums)):
            return
        q = self._by_number.get(wrong_nums[row])
        if q is None:
            return

        from .base_dialog import BaseDialog
        from .question_detail_card import QuestionDetailCard

        dialog = BaseDialog(self, f"错题详情 · 第 {q.number} 题", width=560, height=520)
        v = QVBoxLayout(dialog)
        v.setContentsMargins(28, 24, 28, 20)
        card = QuestionDetailCard(on_option_click=None)
        v.addWidget(card)
        card.show_question(
            q,
            meta_lines=("错题本", f"{type_label(q.type)} · 题号 {q.number}"),
            reveal_answer=True,
        )
        dialog.exec()

    # -------------------------------------------------------------- 练习
    def start_practice(self) -> None:
        """开始错题练习：错题本为空时提示；否则建快照队列切入练习视图。"""
        wrong_nums = self.app_state.get_wrong_questions()
        if not wrong_nums:
            QMessageBox.information(self, "提示", "错题本是空的，先去练习模式刷题吧！")
            return
        wrong_questions = [self._by_number[n] for n in wrong_nums if n in self._by_number]
        if not wrong_questions:
            QMessageBox.information(self, "提示", "错题数据异常，无法开始练习。")
            return

        # 销毁旧 panel（防重复开练习泄漏）
        if self.panel is not None:
            self.panel.deleteLater()
            self.panel = None

        self.practice_engine = QuizEngine(wrong_questions)
        self.practice_session = PracticeSession(self.practice_engine, self.app_state)
        self.panel = PracticePanel(
            self.practice_session,
            self.app_state,
            on_finish=self._on_practice_finished,
            on_submit=self._on_answer_submitted,
            on_navigate=None,
            on_restart=self.start_practice,
        )
        self.stack.addWidget(self.panel)
        self.stack.setCurrentWidget(self.panel)
        self.panel.reset_session(shuffle=False)

    def _on_answer_submitted(self) -> None:
        """错题练习提交后：判题已由 PracticePanel 内部处理，这里做防抖保存。"""
        self._save_progress_delayed()
        self.state_changed.emit()

    def _on_practice_finished(self) -> None:
        """错题队列完成：统计 + 询问移除答对题 + 回列表。"""
        _ = self.app_state.get_practice_stats()  # 占位读取，实际用 engine 统计
        if self.practice_engine is None:
            return
        report = self.practice_engine.get_stats()
        answer = QMessageBox.question(
            self,
            "练习完成",
            f"本次错题练习完成！\n\n"
            f"共答 {report['total']} 题，答对 {report['correct']} 题。\n\n"
            f"是否将本次答对的题目从错题本中移除？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            for num in self.practice_engine.get_correct_question_numbers():
                self.app_state.remove_wrong_question(num)
            if not self.app_state.save_safe():
                QMessageBox.warning(self, "保存失败", self._save_failure_message)

        self._back_to_list()
        self.state_changed.emit()

    def _back_to_list(self) -> None:
        """回列表视图并刷新。"""
        if self.panel is not None:
            self.panel.deleteLater()
            self.panel = None
            self.practice_session = None
        self.stack.setCurrentIndex(0)
        self._refresh_table()

    def _clear_wrong_book(self) -> None:
        """清空错题本（确认后清空 + 立即保存）。"""
        if not self.app_state.wrong_count():
            QMessageBox.information(self, "提示", "错题本已经是空的。")
            return
        answer = QMessageBox.question(
            self,
            "清空错题本",
            "确定要清空所有错题记录吗？此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.app_state.set_wrong_questions([])
        if not self.app_state.save_safe():
            QMessageBox.warning(self, "保存失败", self._save_failure_message)
        self._refresh_table()
        self.state_changed.emit()

    # -------------------------------------------------------------- 主窗口协议
    def on_letter(self, letter: str) -> None:
        """练习视图中 A-D → 选项点击；列表视图无语义。"""
        if self.stack.currentIndex() == 1 and self.panel is not None and self.practice_session:
            if not self.practice_session.is_answered:
                self.panel.handle_option_click(letter)

    def on_submit(self) -> None:
        if self.stack.currentIndex() == 1 and self.panel is not None:
            self.panel.submit_answer()

    def on_prev(self) -> None:
        if self.stack.currentIndex() == 1 and self.panel is not None:
            self.panel.prev_question()

    def on_next(self) -> None:
        if self.stack.currentIndex() == 1 and self.panel is not None:
            self.panel.next_question()

    def nav_count(self) -> str:
        return str(self.app_state.wrong_count())

    def modeline_text(self) -> str:
        if self.stack.currentIndex() == 1 and self.practice_engine is not None:
            return (
                f"WRONGBOOK · 错题练习 第 {self.practice_engine.get_current_index() + 1}"
                f"/{self.practice_engine.queue_length()} 题"
            )
        return f"WRONGBOOK · 错题 {self.app_state.wrong_count()} 题"
