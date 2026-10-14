"""顶部 Header 组件：模式标题、授权状态、全局统计、激活按钮。

2026-10-14 重设计：白底细栏（48px）+ 圆角激活按钮；统计/授权文案
保持既有格式（测试断言依赖），视觉层级靠字重与明度。
"""

import tkinter as tk
from typing import Callable

from .theme import create_primary_button, font_display, font_ui, theme

from license import LicenseStatus


class Header(tk.Frame):
    """主窗口顶部 Header。

    负责展示当前模式名称、授权/题库状态、全局练习统计，
    以及试用版下的「输入注册码」按钮。
    """

    def __init__(
        self,
        parent: tk.Misc,
        license_status: LicenseStatus | None = None,
        total_count: int = 0,
        trial_count: int = 0,
        on_activate_click: Callable[[], None] | None = None,
        mode_title: str = "练习",
    ) -> None:
        """初始化 Header。

        Args:
            parent: 父容器
            license_status: LicenseStatus 枚举值或 None
            total_count: 题库总题数
            trial_count: 试用版可练习题数
            on_activate_click: 「输入注册码」按钮点击回调
            mode_title: 初始模式标题
        """
        super().__init__(parent, bg=theme.BG_CARD, height=48)
        self.pack_propagate(False)
        self.license_status = license_status
        self.total_count = total_count
        self.trial_count = trial_count
        self.on_activate_click = on_activate_click
        self.activate_btn: tk.Canvas | None = None

        self._build()
        self.set_mode_title(mode_title)

    def _build(self) -> None:
        inner = tk.Frame(self, bg=theme.BG_CARD)
        inner.pack(fill=tk.BOTH, expand=True, padx=20)

        self.mode_title = tk.Label(
            inner, text="", font=font_display(15, True), fg=theme.TEXT_PRIMARY, bg=theme.BG_CARD
        )
        self.mode_title.pack(side=tk.LEFT, pady=10)

        self.license_status_label = tk.Label(
            inner, text="", font=font_ui(10), fg=theme.TEXT_MUTED, bg=theme.BG_CARD
        )
        self.license_status_label.pack(side=tk.LEFT, padx=(12, 0), pady=10)

        self.stats_label = tk.Label(
            inner, text="", font=font_ui(10), fg=theme.TEXT_MUTED, bg=theme.BG_CARD
        )
        self.stats_label.pack(side=tk.RIGHT, pady=10)

        if self.license_status != LicenseStatus.AUTHORIZED:
            self.activate_btn = create_primary_button(
                inner,
                text="输入注册码",
                command=self._on_activate_click,
                padx=12,
                pady=3,
            )
            self.activate_btn.pack(side=tk.RIGHT, padx=(8, 0), pady=8)
        else:
            self.activate_btn = None

        self._refresh_license_text()

    def _on_activate_click(self) -> None:
        if self.on_activate_click:
            self.on_activate_click()

    def _refresh_license_text(self) -> None:
        if self.license_status == LicenseStatus.AUTHORIZED:
            text = f"题库共 {self.total_count} 题 · 已授权"
        else:
            text = f"题库共 {self.total_count} 题 · 试用版（前 {self.trial_count} 题）"
        self.license_status_label.configure(text=text)

    def set_mode_title(self, title: str) -> None:
        """更新当前模式标题。"""
        self.mode_title.configure(text=title)

    def update_stats(self, practiced: int, accuracy: float, wrong_count: int) -> None:
        """更新全局统计标签。

        Args:
            practiced: 已练习题数
            accuracy: 正确率（0.0 ~ 100.0）
            wrong_count: 错题数量
        """
        self.stats_label.configure(
            text=(f"已练 {practiced} 题  ·  正确率 {accuracy:.0f}%  ·  错题 {wrong_count}")
        )
