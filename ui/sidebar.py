"""侧边栏组件：品牌、Pill 导航、就绪度环 Hero、错题指示、主题切换。

2026-10-14 重设计：tk.Frame 直角深栏 → RoundedCard 浮动深色圆角卡
（浮于冷灰蓝页面）；导航改 Pill 选中态 + 线性图标；就绪度环升级为
104px 分段渐变弧 Hero，下挂覆盖率 / 正确率双指标；底部主题切换按钮
（moon/sun，命令由 MainWindow 注入，见 P4 双主题接线）。
"""

import tkinter as tk
from functools import partial
from typing import Callable

from .constants import NAV_ITEM_HEIGHT, SIDEBAR_WIDTH
from .icons import draw_icon
from .mastery_ring import MasteryRing
from .rounded import Chip, IconButton, RoundedCard, draw_round_rect
from .theme import create_chip, font_display, font_ui, font_ui_semibold, theme

# 导航图标名（与 icons.py 注册表对应）
_NAV_ICONS = {
    "practice": "practice",
    "exam": "exam",
    "review": "review",
    "wrong": "wrong",
}


class _NavPill(RoundedCard):
    """单个导航项（Pill 圆角卡片 + 线性图标 + 文字）。

    选中态：云蓝底白字；默认：与侧栏同底（隐形），hover 浮出 INK_SOFT。
    takefocus + Return/Space 键盘激活（对标 P0-7 可达性模式）。
    """

    def __init__(
        self,
        parent: tk.Misc,
        icon: str,
        text: str,
        on_click: Callable[[], None],
    ) -> None:
        super().__init__(parent, radius=8, bg=theme.INK, surface=theme.INK, padx=10, pady=7)
        self.configure(cursor="hand2", takefocus=True, height=NAV_ITEM_HEIGHT)
        self._icon_name = icon
        self._text = text
        self._on_click = on_click
        self._active = False

        self._icon = tk.Canvas(
            self.inner, width=16, height=16, bg=theme.INK, highlightthickness=0, bd=0
        )
        draw_icon(self._icon, icon, 8, 8, 16, theme.INK_TEXT_MUTED)
        self._icon.pack(side=tk.LEFT)

        self._label = tk.Label(
            self.inner,
            text=text,
            font=font_ui(12),
            fg=theme.INK_TEXT_MUTED,
            bg=theme.INK,
            anchor="w",
        )
        self._label.pack(side=tk.LEFT, padx=(10, 0))

        for w in (self, self.inner, self._icon, self._label):
            w.bind("<Button-1>", self._handle_click)
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)
            w.configure(cursor="hand2")
        self.bind("<Return>", self._handle_click)
        self.bind("<space>", self._handle_click)

    # ---------------------------------------------------------------- 交互
    def _handle_click(self, event: tk.Event | None = None) -> str:
        self._on_click()
        return "break"

    def _on_enter(self, event: tk.Event | None = None) -> None:
        if not self._active:
            self._paint(bg=theme.INK_SOFT, fg=theme.INK_TEXT, icon_color=theme.INK_TEXT, bold=False)

    def _on_leave(self, event: tk.Event | None = None) -> None:
        if not self._active:
            self._paint(
                bg=theme.INK, fg=theme.INK_TEXT_MUTED, icon_color=theme.INK_TEXT_MUTED, bold=False
            )

    # ---------------------------------------------------------------- 状态
    def set_active(self, active: bool) -> None:
        self._active = active
        if active:
            self._paint(bg=theme.ACCENT, fg=theme.INK_TEXT, icon_color="#ffffff", bold=True)
        else:
            self._paint(
                bg=theme.INK, fg=theme.INK_TEXT_MUTED, icon_color=theme.INK_TEXT_MUTED, bold=False
            )

    def _paint(self, *, bg: str, fg: str, icon_color: str, bold: bool) -> None:
        self.set_style(bg=bg)
        self._icon.configure(bg=bg)
        self._icon.delete("all")
        draw_icon(self._icon, self._icon_name, 8, 8, 16, icon_color)
        self._label.configure(bg=bg, fg=fg, font=font_ui_semibold(12) if bold else font_ui(12))


class Sidebar(RoundedCard):
    """主窗口左侧浮动侧栏（深色圆角卡）。

    负责品牌、Pill 导航、就绪度环 Hero、错题指示器、主题切换按钮的
    构建与状态更新。导航点击直接执行 nav_defs 中的 command，不直接
    依赖主窗口内部状态。

    Args:
        parent: 父容器
        nav_defs: [(tab_id, tab_text, command), ...] 导航定义
        on_theme_toggle: 主题切换回调（MainWindow.toggle_theme）；None 时按钮为空操作
    """

    def __init__(
        self,
        parent: tk.Misc,
        nav_defs: list[tuple[str, str, Callable[[], None] | None]],
        on_theme_toggle: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent, radius=14, bg=theme.INK, surface=theme.BG_PAGE, padx=14, pady=18)
        self.configure(width=SIDEBAR_WIDTH)
        self._nav_defs = nav_defs
        self._active_nav = nav_defs[0][0] if nav_defs else None
        self._nav_pills: dict[str, _NavPill] = {}
        self.mastery_ring: MasteryRing | None = None
        self.wrong_indicator: Chip | None = None
        self.theme_btn: IconButton | None = None
        self.coverage_label: tk.Label | None = None
        self.accuracy_label: tk.Label | None = None
        self._on_theme_toggle = on_theme_toggle
        self._build()

    # ------------------------------------------------------------------ 构建
    def _build(self) -> None:
        # 品牌块
        brand = tk.Frame(self.inner, bg=theme.INK)
        brand.pack(fill=tk.X)

        logo = tk.Canvas(brand, width=28, height=28, bg=theme.INK, highlightthickness=0, bd=0)
        draw_round_rect(logo, 0, 0, 28, 28, 7, fill=theme.ACCENT)
        logo.create_text(
            14, 14, text="ACP", font=("Arial", 9, "bold"), fill="#ffffff", anchor="center"
        )
        logo.pack(side=tk.LEFT)

        name_box = tk.Frame(brand, bg=theme.INK)
        name_box.pack(side=tk.LEFT, padx=(10, 0))
        tk.Label(
            name_box,
            text="云计算练习",
            font=font_display(13, True),
            fg=theme.INK_TEXT,
            bg=theme.INK,
            anchor="w",
        ).pack(anchor="w")
        tk.Label(
            name_box,
            text="ACP 认证备考",
            font=font_ui(9),
            fg=theme.INK_TEXT_MUTED,
            bg=theme.INK,
            anchor="w",
        ).pack(anchor="w")

        # 分隔
        tk.Frame(self.inner, bg=theme.INK_DIVIDER, height=1).pack(fill=tk.X, pady=(14, 12))

        # Pill 导航
        for tab_id, tab_text, command in self._nav_defs:
            self._build_nav_item(tab_id, tab_text, command)

        # 弹性空间，把 Hero 区推到底部
        tk.Frame(self.inner, bg=theme.INK).pack(fill=tk.BOTH, expand=True)

        # 就绪度环 Hero
        ring_wrap = tk.Frame(self.inner, bg=theme.INK)
        ring_wrap.pack(anchor="center")
        self.mastery_ring = MasteryRing(ring_wrap)
        self.mastery_ring.pack()

        # 双指标
        self.coverage_label = tk.Label(
            self.inner, text="覆盖率 —", font=font_ui(10), fg=theme.INK_TEXT_MUTED, bg=theme.INK
        )
        self.coverage_label.pack(anchor="center", pady=(10, 0))
        self.accuracy_label = tk.Label(
            self.inner, text="正确率 —", font=font_ui(10), fg=theme.INK_TEXT_MUTED, bg=theme.INK
        )
        self.accuracy_label.pack(anchor="center")

        # 错题指示 pill
        self.wrong_indicator = create_chip(
            self.inner, text="错题本为空", bg=theme.INK_SOFT, fg=theme.INK_TEXT_MUTED
        )
        self.wrong_indicator.pack(anchor="center", pady=(12, 0))

        # 主题切换按钮
        self.theme_btn = IconButton(
            self.inner,
            icon="moon",
            command=self._handle_theme_toggle,
            bg=theme.INK_SOFT,
            hover_bg=theme.ACCENT,
            fg=theme.INK_TEXT_MUTED,
            size=30,
        )
        self.theme_btn.pack(anchor="center", pady=(12, 0))

        self._update_nav_highlight()

    def _build_nav_item(
        self,
        tab_id: str,
        tab_text: str,
        command: Callable[[], None] | None,
    ) -> None:
        icon = _NAV_ICONS.get(tab_id, "practice")
        # Pill 点击统一走 _handle_nav_click（去重 + 高亮 + 执行），
        # 与测试及旧 API 语义一致
        pill = _NavPill(self.inner, icon, tab_text, partial(self._handle_nav_click, tab_id))
        pill.pack(fill=tk.X, pady=3)
        self._nav_pills[tab_id] = pill

    # ---------------------------------------------------------------- 交互
    def _handle_nav_click(self, tab_id: str) -> None:
        """处理导航项点击：更新高亮并执行命令。

        重复点击当前 tab 不触发 command（P2-14：避免销毁重建丢失
        答题进度/筛选状态）。Pill 点击与外部调用（测试）共用本入口。
        """
        if tab_id == self._active_nav:
            return
        self.set_active_nav(tab_id)
        for tid, _text, command in self._nav_defs:
            if tid == tab_id and command is not None:
                command()
                return

    def _handle_theme_toggle(self) -> None:
        if self._on_theme_toggle is not None:
            self._on_theme_toggle()

    def set_theme_icon(self, mode: str) -> None:
        """同步主题切换按钮图标（深色下显示 sun，浅色下显示 moon）。"""
        if self.theme_btn is not None:
            self.theme_btn.configure(icon="sun" if mode == "dark" else "moon")

    # ---------------------------------------------------------------- 状态
    def set_active_nav(self, tab_id: str) -> None:
        """设置当前活动导航项并更新高亮。"""
        self._active_nav = tab_id
        self._update_nav_highlight()

    def _update_nav_highlight(self) -> None:
        for tab_id, pill in self._nav_pills.items():
            pill.set_active(tab_id == self._active_nav)

    def set_mastery(self, mastery: float) -> None:
        """更新就绪度环。"""
        if self.mastery_ring is not None:
            self.mastery_ring.set_mastery(mastery)

    def set_readiness_stats(self, coverage: float, accuracy: float) -> None:
        """更新环下双指标（覆盖率 / 正确率，0.0 ~ 1.0）。"""
        if self.coverage_label is not None:
            self.coverage_label.configure(text=f"覆盖率 {coverage * 100:.0f}%")
        if self.accuracy_label is not None:
            self.accuracy_label.configure(text=f"正确率 {accuracy * 100:.0f}%")

    def set_wrong_indicator(self, text: str, fg: str | None = None) -> None:
        """更新错题指示器文本与颜色。"""
        if self.wrong_indicator is not None:
            kwargs: dict[str, object] = {"text": text}
            if fg is not None:
                kwargs["fg"] = fg
            self.wrong_indicator.configure(**kwargs)
