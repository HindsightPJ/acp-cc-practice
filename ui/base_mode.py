"""模式页基类：防抖保存 + 主窗口鸭子协议默认实现。

PySide6 版（tkinter BaseMode 重写）：
- 防抖保存三件套收敛为单发 QTimer（restart 语义 = 重置计时），
  替代 tkinter after/after_cancel 的 job id 跟踪与集合去重；
- 键盘处理已上移 MainWindow 的 QShortcut 路由（on_letter/on_submit/
  on_prev/on_next 鸭子转发），本类不再绑定键盘事件；
- 主窗口协作协议（P3 决策）：nav_count()/modeline_text() 返回 None
  时主窗口显示缺省值，子类按需覆盖。

线程红线（desktop_python.md §二）：本类只在主线程操作 UI 与状态。
"""

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QFrame, QMessageBox, QWidget

from app_state import AppState

# 防抖保存间隔（毫秒）——原 ui/constants.py SAVE_DEBOUNCE_MS，就近内联
SAVE_DEBOUNCE_MS = 2000


class BaseModePage(QFrame):
    """模式页基类。

    子类在提交 / 导航 / 重置等状态变化时机调用 _save_progress_delayed()，
    并在此之前自行把会话快照同步进 app_state（快照唯一写入口在子类）。

    state_changed 信号：页面内部状态（进度/统计/导航计数）变化后 emit，
    主窗口据此刷新 board-nav 计数与 modeline，避免轮询。
    """

    state_changed = Signal()

    # 子类可覆盖此属性定制保存失败提示文案
    _save_failure_message = "进度保存失败，请检查磁盘空间或文件权限。"

    def __init__(self, app_state: AppState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.app_state = app_state
        self._pending_save = False
        # 单发 QTimer：start() 自带 restart 语义，防抖窗口内新调用自动重置
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._do_save_progress)

    # -------------------------------------------------------------- 防抖保存
    def _save_progress_delayed(self) -> None:
        """标记有待保存的进度，SAVE_DEBOUNCE_MS 后落盘（期间新调用重置计时）。"""
        self._pending_save = True
        self._save_timer.start(SAVE_DEBOUNCE_MS)

    def _do_save_progress(self) -> None:
        """防抖计时到期执行实际保存。"""
        # 先保存成功再清标记：失败时保留待存状态，后续操作可重试
        if self.app_state.save_safe():
            self._pending_save = False
        else:
            QMessageBox.warning(self, "保存失败", self._save_failure_message)

    def flush_pending_save(self) -> None:
        """切页 / 关窗前强制保存延迟的进度，避免数据丢失。

        由 MainWindow 在切换模式页与 closeEvent 时鸭子探测调用；
        无待存进度时为零开销。
        """
        if not self._pending_save:
            return
        self._save_timer.stop()
        if self.app_state.save_safe():
            self._pending_save = False
        else:
            QMessageBox.warning(
                self,
                "保存失败",
                f"{self._save_failure_message}\n\n本次进度可能未落盘。",
            )

    # -------------------------------------------------------------- 主窗口协议
    def nav_count(self) -> str | None:
        """board-nav 右侧计数（None = 显示缺省 '—'）。"""
        return None

    def modeline_text(self) -> str | None:
        """modeline 自定义文案（None = 主窗口用缺省模板）。"""
        return None
