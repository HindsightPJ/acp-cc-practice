"""练习模式页：F 方案网格体（PracticePanel）+ 会话生命周期编排。

tkinter 版重写。视图渲染全部委托 PracticePanel；本类只负责：
- 快照同步（提交 / 导航 / 重置 / 完成 四时机单点汇合 → 防抖落盘）
- 启动时恢复上次练习（practice_progress 快照无效则全新开始）
- 重新开始确认（已有作答时防静默清空）
- 主窗口鸭子协议转发（on_letter/on_submit/on_prev/on_next → panel）
"""

from PySide6.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QMessageBox, QVBoxLayout

from quiz_engine import QuizEngine
from models import Question
from app_state import AppState
from .base_mode import BaseModePage
from .practice_panel import PracticePanel
from .practice_session import PracticeSession


class PracticeMode(BaseModePage):
    """练习模式页。"""

    _save_failure_message = "学习进度保存失败，请检查磁盘空间或文件权限。"

    def __init__(
        self,
        questions: list[Question],
        app_state: AppState,
        parent=None,
    ) -> None:
        super().__init__(app_state, parent)
        self.engine = QuizEngine(questions)
        self.session = PracticeSession(self.engine, self.app_state)
        # 已实际生效的 shuffle 状态（取消"重新开始"时用于回滚复选框显示）
        self._applied_shuffle = False

        self._build_ui()
        self._restore_or_start_session()

    # -------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # 顶部工具行：随机出题开关（F 方案方角复选框，QSS QCheckBox 语义类）
        tools = QFrame()
        th = QHBoxLayout(tools)
        th.setContentsMargins(30, 14, 30, 0)
        th.setSpacing(0)
        th.addStretch(1)
        self.shuffle_check = QCheckBox("随机出题")
        self.shuffle_check.toggled.connect(self._on_shuffle_toggled)
        th.addWidget(self.shuffle_check)
        v.addWidget(tools)

        # P0 修复沿用：on_submit/on_navigate 必须接线，否则防抖保存永不触发
        self.panel = PracticePanel(
            self.session,
            self.app_state,
            on_finish=self._on_practice_finished,
            on_submit=self._on_answer_submitted,
            on_navigate=self._on_navigated,
            on_restart=self.start_new_session,
        )
        v.addWidget(self.panel, 1)

    # -------------------------------------------------------------- 钩子
    def _on_answer_submitted(self) -> None:
        """提交完成后钩子（panel 触发）：防抖保存 + 通知主窗口刷新。"""
        self._save_progress_delayed()
        self.state_changed.emit()

    def _on_navigated(self) -> None:
        """切题后钩子：位置变化也纳入防抖持久化（进度恢复用）。"""
        self._save_progress_delayed()
        self.state_changed.emit()

    def _on_practice_finished(self) -> None:
        """队列完成：快照保持在末题状态，提示完成。"""
        self._save_progress_delayed()
        self.state_changed.emit()
        QMessageBox.information(self, "提示", "已完成所有题目！")

    def _save_progress_delayed(self) -> None:
        """先同步练习会话快照，再走基类防抖落盘（快照唯一写入口）。"""
        self.app_state.set_practice_progress(self.session.export_state())
        super()._save_progress_delayed()

    # -------------------------------------------------------------- 会话生命周期
    def _restore_or_start_session(self) -> None:
        """启动时尝试恢复上次练习（进度恢复）；快照无效则全新开始。"""
        state = self.app_state.get_practice_progress()
        if state and self.session.restore_state(state):
            self._applied_shuffle = bool(state.get("shuffle", False))
            self.shuffle_check.setChecked(self._applied_shuffle)
            self.panel.sheet.build_rows(self.engine.queue_length())
            self.panel.load_current_question()
        else:
            self.panel.reset_session(shuffle=False)

    def start_new_session(self) -> None:
        """重新开始：已有作答时先确认，避免静默清空当前进度。"""
        new_shuffle = self.shuffle_check.isChecked()
        if self.engine.has_answers():
            answer = QMessageBox.question(
                self,
                "重新开始",
                "当前作答记录将被清空，确定重新开始吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                # 取消：回滚复选框到实际生效的状态（toggled 已翻转它）
                self.shuffle_check.setChecked(self._applied_shuffle)
                return
        self._applied_shuffle = new_shuffle
        self.panel.reset_session(shuffle=new_shuffle)
        self._save_progress_delayed()
        self.state_changed.emit()

    def _on_shuffle_toggled(self, checked: bool) -> None:
        """复选框切换仅在"重新开始"时生效（与 tkinter 版语义一致）。"""
        _ = checked  # 状态由 start_new_session 读取；此处仅占位接信号

    # -------------------------------------------------------------- 主窗口协议
    def on_letter(self, letter: str) -> None:
        """快捷键 A-D → 选项点击（未提交才有效，session 内部判定）。"""
        if not self.session.is_answered:
            self.panel.handle_option_click(letter)

    def on_submit(self) -> None:
        """快捷键 Enter → 提交。"""
        self.panel.submit_answer()

    def on_prev(self) -> None:
        self.panel.prev_question()

    def on_next(self) -> None:
        self.panel.next_question()

    def nav_count(self) -> str:
        return self.panel.nav_count()

    def modeline_text(self) -> str:
        return self.panel.modeline_text()
