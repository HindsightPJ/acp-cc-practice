"""对话框基类，封装 Toplevel 创建、模态设置、居中、关闭等公共逻辑。"""

import tkinter as tk

from .theme import center_window, theme


class BaseDialog:
    """模态对话框基类。

    子类在 show() 中调用 _create_dialog() 创建窗口，然后构建内容。
    通过 close() 安全关闭。

    Args:
        parent: 父窗口
        title: 对话框标题
        size: 窗口尺寸，如 "500x400"
        center: 是否居中显示（默认 True）
    """

    def __init__(
        self,
        parent: tk.Misc,
        title: str,
        size: str = "500x400",
        center: bool = True,
    ) -> None:
        self.parent = parent
        self.dialog: tk.Toplevel | None = None
        self._title = title
        self._size = size
        self._center = center
        # P1: after 任务跟踪（与 BaseMode._after_jobs 同语义），close 时统一取消
        self._after_jobs: set[str] = set()

    def _create_dialog(self) -> None:
        """创建 Toplevel 并设置标题、尺寸、背景色、模态、居中。"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title(self._title)
        self.dialog.geometry(self._size)
        self.dialog.configure(bg=theme.BG_PAGE)
        self.dialog.transient(self.parent.winfo_toplevel())
        # P1: 拦截标题栏 X——直接销毁会让 self.dialog 悬挂为已销毁对象，
        # 异步回包/轮询打上去会抛 TclError；统一走 close() 清理
        self.dialog.protocol("WM_DELETE_WINDOW", self.close)
        self.dialog.grab_set()

        if self._center:
            self._center_dialog()

    def _add_after_job(self, job_id: str) -> None:
        """登记 after 任务（集合自动去重）。"""
        self._after_jobs.add(job_id)

    def _cancel_after_job(self, job_id: str | None) -> None:
        """取消单个 after 任务并移出跟踪集合（cancel + discard 统一语义）。"""
        if job_id is None:
            return
        try:
            if self.dialog is not None:
                self.dialog.after_cancel(job_id)
        except tk.TclError:
            pass  # widget 已销毁或 job 已执行（与 BaseMode 同语义）
        self._after_jobs.discard(job_id)

    def _cancel_all_after_jobs(self) -> None:
        """取消全部待执行的 after 任务（close 前调用）。"""
        for job_id in self._after_jobs:
            try:
                if self.dialog is not None:
                    self.dialog.after_cancel(job_id)
            except tk.TclError:
                pass  # widget 已销毁或 job 已执行
        self._after_jobs.clear()

    def _center_dialog(self) -> None:
        """将对话框居中到屏幕中央。"""
        if self.dialog is None:
            return
        center_window(self.dialog)

    def close(self) -> None:
        """安全关闭对话框：先取消全部 after 任务，再销毁窗口。"""
        self._cancel_all_after_jobs()
        if self.dialog is not None:
            try:
                self.dialog.destroy()
            except tk.TclError:
                pass
            self.dialog = None
