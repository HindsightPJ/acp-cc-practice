"""对话框基类，封装 Toplevel 创建、模态设置、居中、关闭等公共逻辑。"""

import tkinter as tk

from .theme import theme


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

    def _create_dialog(self) -> None:
        """创建 Toplevel 并设置标题、尺寸、背景色、模态、居中。"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title(self._title)
        self.dialog.geometry(self._size)
        self.dialog.configure(bg=theme.BG_PAGE)
        self.dialog.transient(self.parent.winfo_toplevel())
        self.dialog.grab_set()

        if self._center:
            self._center_dialog()

    def _center_dialog(self) -> None:
        """将对话框居中到屏幕中央。"""
        if self.dialog is None:
            return
        self.dialog.update_idletasks()
        width = self.dialog.winfo_width()
        height = self.dialog.winfo_height()
        x = (self.dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (height // 2)
        self.dialog.geometry(f"{width}x{height}+{x}+{y}")

    def close(self) -> None:
        """安全关闭对话框。"""
        if self.dialog is not None:
            try:
                self.dialog.destroy()
            except tk.TclError:
                pass
            self.dialog = None
