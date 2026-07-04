"""ModeToolbar - 模式页面顶部工具栏统一组件。

消除 PracticeMode / ReviewMode / WrongBook 中重复出现的
`toolbar` / `toolbar_left` / `toolbar_right` 三段式框架样板代码。
调用方将子控件直接 pack 到 `toolbar.left` 或 `toolbar.right` 容器中。
"""

import tkinter as tk

from .theme import theme


class ModeToolbar(tk.Frame):
    """模式页面顶部工具栏。

    结构：左侧容器（靠左）+ 右侧容器（靠右），背景色统一为 BG_PAGE。
    调用方负责创建和 pack 子控件。
    """

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, bg=theme.BG_PAGE)
        self.pack(fill=tk.X, pady=(0, 12))

        self.left = tk.Frame(self, bg=theme.BG_PAGE)
        self.left.pack(side=tk.LEFT)

        self.right = tk.Frame(self, bg=theme.BG_PAGE)
        self.right.pack(side=tk.RIGHT)
