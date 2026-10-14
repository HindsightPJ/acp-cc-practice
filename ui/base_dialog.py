"""模态对话框基类（QDialog 版）。

PySide6 QDialog 自带模态（exec()）、父窗口归属与 Esc 关闭，
基类只统一：标题、默认尺寸、居中策略与 QSS 尺寸约定。
子类构建内容后由调用方 exec()，结果经 StandardButton/accept() 返回。

对话框沿用系统标题栏（模态弹窗为 Windows 常态；Frameless 仅主窗口），
内容区走 F 方案排版：4px 规则线分段、无卡片、单一强调色。
"""

from PySide6.QtWidgets import QDialog, QWidget


class BaseDialog(QDialog):
    """模态对话框基类。

    Args:
        parent: 父窗口（QSS 继承与窗口归属）
        title: 对话框标题
        width/height: 内容区尺寸；None = 由内容决定
    """

    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        width: int | None = None,
        height: int | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        if width and height:
            self.resize(width, height)
