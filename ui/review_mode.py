"""背题模式页：全题库浏览 + 收藏筛选 + 自动显示答案。

tkinter 版重写。视图 = 顶部工具行 + QuestionDetailCard（只读，无选项点击）。

键盘协议（MainWindow 单点路由）：Enter = 显示/隐藏答案（沿袭 tkinter
版 Space 语义，统一收敛到 on_submit 路由，键盘协议单点）；
←/→ = 翻题；A-D 在背题模式无语义。
"""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from app_state import AppState
from models import Question
from quiz_engine import QuizEngine
from .base_mode import BaseModePage
from .question_detail_card import QuestionDetailCard

# 自动显示答案延时（原 ui/constants.py AUTO_SHOW_ANSWER_DELAY_MS，就近内联）
AUTO_SHOW_ANSWER_DELAY_MS = 100


class ReviewMode(BaseModePage):
    """背题模式页。"""

    def __init__(
        self,
        questions: list[Question],
        app_state: AppState,
        parent=None,
    ) -> None:
        super().__init__(app_state, parent)
        self.all_questions = questions
        self.engine = QuizEngine(questions)
        self.favorites_only = False

        # 单发定时器：自动显示答案（load_question 时 restart，天然防抖）
        self._auto_show_timer = QTimer(self)
        self._auto_show_timer.setSingleShot(True)
        self._auto_show_timer.timeout.connect(self._auto_show_answer)

        self._build_ui()
        # 背题浏览 = 全题库原序队列（QuizEngine 构造后队列为空，需显式启动）
        self.engine.start_practice_mode(shuffle=False)
        self.load_question()

    # -------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # 顶部工具行（F 方案无卡片：一条 1px 规则线下的工具带）
        tools = QFrame()
        th = QHBoxLayout(tools)
        th.setContentsMargins(30, 14, 30, 14)
        th.setSpacing(18)

        self.fav_check = QCheckBox("只看收藏")
        self.fav_check.toggled.connect(self.toggle_favorites_filter)
        th.addWidget(self.fav_check)

        self.auto_check = QCheckBox("自动显示答案")
        self.auto_check.toggled.connect(self._on_auto_toggled)
        th.addWidget(self.auto_check)

        th.addStretch(1)

        self.progress_label = QLabel()
        self.progress_label.setProperty("qMeta", True)
        th.addWidget(self.progress_label)

        th.addWidget(QLabel("跳转"))
        self.jump_edit = QLineEdit()
        self.jump_edit.setPlaceholderText("题号")
        self.jump_edit.setFixedWidth(72)
        self.jump_edit.returnPressed.connect(self._jump_from_input)
        th.addWidget(self.jump_edit)

        prev_btn = QPushButton("←")
        prev_btn.setProperty("actBtn", True)
        prev_btn.clicked.connect(self.prev_question)
        th.addWidget(prev_btn)

        next_btn = QPushButton("→")
        next_btn.setProperty("actBtn", True)
        next_btn.clicked.connect(self.next_question)
        th.addWidget(next_btn)

        # 收藏入口（补 tkinter 版缺口：此前迁移漏掉收藏按钮，收藏功能成死路）
        self.favorite_btn = QPushButton()
        self.favorite_btn.setProperty("actBtn", True)
        self.favorite_btn.clicked.connect(self.toggle_favorite)
        th.addWidget(self.favorite_btn)

        v.addWidget(tools)

        # 题区（只读详情卡：on_option_click=None，解析占位 = 答案提示）
        body = QFrame()
        bv = QVBoxLayout(body)
        bv.setContentsMargins(30, 0, 30, 22)
        self.detail_card = QuestionDetailCard(
            on_option_click=None, answer_placeholder="按 Enter 显示答案与解析"
        )
        bv.addWidget(self.detail_card)
        v.addWidget(body, 1)

    # -------------------------------------------------------------- 数据
    def _favorite_questions(self) -> list[Question]:
        """收藏题号 → 题目列表（保持题库原序）。"""
        favs = set(self.app_state.get_favorites())
        return [q for q in self.all_questions if q.number in favs]

    def load_question(self) -> None:
        """渲染当前题 + 自动显示答案调度。"""
        question = self.engine.get_current_question()
        if question is None:
            self.detail_card.show_question(
                self.all_questions[0] if self.all_questions else Question(0, "题库为空"),
                meta_lines=("背题模式", "无题目"),
            )
            self.progress_label.setText("无题目")
            return

        current = self.engine.get_current_index()
        total = self.engine.queue_length()
        self.progress_label.setText(f"第 {current + 1} / {total} 题")

        self.detail_card.show_question(
            question,
            meta_lines=("背题模式", f"第 {current + 1} / {total} 题"),
        )
        self._sync_favorite_button()
        if self.auto_check.isChecked():
            self._auto_show_timer.start(AUTO_SHOW_ANSWER_DELAY_MS)

    def _auto_show_answer(self) -> None:
        """自动显示答案（QTimer 到期，仅在开关开启时生效）。"""
        if self.auto_check.isChecked():
            self._render_answer()

    def _render_answer(self) -> None:
        """渲染正确答案与解析（自动显示与手动 Enter 共用）。"""
        question = self.engine.get_current_question()
        if question is not None:
            self.detail_card.reveal_correct_options(question)
            self.detail_card.set_verdict(f"正确答案: {question.answer or '未知'}", ok=True)
            self.detail_card.set_explanation(question.explanation or "暂无解析")

    def toggle_answer(self) -> None:
        """显示/隐藏答案与解析（Enter 路由）。"""
        if self._auto_show_timer.isActive():
            self._auto_show_timer.stop()
            self.detail_card.clear_answer_state()
            return
        if self.detail_card.exp_result.property("verdict") is not None:
            self.detail_card.clear_answer_state()
        else:
            self._render_answer()

    # -------------------------------------------------------------- 筛选/导航
    def toggle_favorite(self) -> None:
        """收藏/取消收藏当前题（收藏按钮触发），防抖保存并同步按钮文案。

        筛选模式下取消收藏时，当前题移出队列并加载下一题（沿袭 tkinter 版）。
        """
        question = self.engine.get_current_question()
        if question is None:
            return
        self.app_state.toggle_favorite(question.number)
        if self.favorites_only and not self.app_state.is_favorite(question.number):
            # 取消收藏后重建筛选队列（当前题号出队，位置从 0 重新加载）
            self.toggle_favorites_filter(True)
        else:
            self._sync_favorite_button()
        self._save_progress_delayed()
        self.state_changed.emit()

    def _sync_favorite_button(self) -> None:
        """收藏按钮文案随当前题收藏状态变化。"""
        question = self.engine.get_current_question()
        fav = question is not None and self.app_state.is_favorite(question.number)
        self.favorite_btn.setText("★ 已收藏" if fav else "收藏")

    def toggle_favorites_filter(self, checked: bool) -> None:
        """只看收藏：重建引擎队列（收藏题列表），位置重置。"""
        self._auto_show_timer.stop()
        self.favorites_only = checked
        queue = self._favorite_questions() if checked else self.all_questions
        self.engine = QuizEngine(queue)
        self.engine.start_practice_mode(shuffle=False)
        if not queue:
            self.detail_card.show_question(
                Question(0, "暂无收藏题目"), meta_lines=("背题模式", "收藏夹为空")
            )
            self.progress_label.setText("0 / 0 题")
            self.state_changed.emit()
            return
        self.load_question()

    def _jump_from_input(self) -> None:
        """跳转输入框：1-based 题号 → 队列索引。"""
        text = self.jump_edit.text().strip()
        if not text.isdigit():
            self.jump_edit.clear()
            return
        target = int(text) - 1
        if 0 <= target < self.engine.queue_length():
            self.engine.set_current_index(target)
            self.load_question()
        self.jump_edit.clear()

    def next_question(self) -> None:
        if self.engine.has_next():
            self.engine.next_question()
            self.load_question()
            self.state_changed.emit()

    def prev_question(self) -> None:
        if self.engine.has_prev():
            self.engine.prev_question()
            self.load_question()
            self.state_changed.emit()

    def _on_auto_toggled(self, checked: bool) -> None:
        """开关自动显示答案：开启时立即显示当前题，关闭时清除。"""
        if checked:
            self._auto_show_answer()
        else:
            self._auto_show_timer.stop()
            self.detail_card.clear_answer_state()

    # -------------------------------------------------------------- 主窗口协议
    def on_submit(self) -> None:
        """Enter = 显示/隐藏答案（沿袭 tkinter 版 Space 语义）。"""
        self.toggle_answer()

    def on_prev(self) -> None:
        self.prev_question()

    def on_next(self) -> None:
        self.next_question()

    def nav_count(self) -> str:
        total = self.engine.queue_length()
        if total == 0:
            return "0/0"
        return f"{self.engine.get_current_index() + 1}/{total}"

    def modeline_text(self) -> str:
        scope = "收藏" if self.favorites_only else "全库"
        return (
            f"REVIEW({scope}) · 第 {self.engine.get_current_index() + 1}"
            f"/{self.engine.queue_length()} 题 · 收藏 {self.app_state.favorites_count()}"
        )
