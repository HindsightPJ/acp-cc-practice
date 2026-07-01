"""侧边栏组件：品牌、导航、就绪度环、错题指示器。"""
import tkinter as tk
from typing import List, Dict, Any, Optional, Callable

from .theme import (
    INK, INK_TEXT, INK_TEXT_MUTED, INK_DIVIDER,
    ACCENT,
    RED,
    font_ui, font_ui_semibold, font_display,
)
from .mastery_ring import MasteryRing


SIDEBAR_WIDTH = 200


class Sidebar(tk.Frame):
    """主窗口左侧边栏。

    负责品牌、导航项、就绪度环、错题指示器的构建与状态更新。
    通过回调与 MainWindow 通信，避免直接依赖主窗口内部状态。
    """

    def __init__(self, parent, nav_defs: List[tuple],
                 on_nav_clicked: Optional[Callable[[str], None]] = None) -> None:
        """初始化侧边栏。

        Args:
            parent: 父容器
            nav_defs: [(tab_id, tab_text, command), ...] 导航定义
            on_nav_clicked: 点击导航项后的外部回调，签名为 (tab_id) -> None
        """
        super().__init__(parent, bg=INK, width=SIDEBAR_WIDTH)
        self.pack_propagate(False)
        self._nav_defs = nav_defs
        self._on_nav_clicked = on_nav_clicked
        self._active_nav = nav_defs[0][0] if nav_defs else None
        self._nav_refs = {}
        self.mastery_ring = None
        self.wrong_indicator = None
        self._build()

    def _build(self):
        # 品牌
        brand = tk.Frame(self, bg=INK)
        brand.pack(fill=tk.X, padx=20, pady=(20, 16))

        tk.Label(brand, text="ACP",
                 font=font_display(20, True),
                 fg=ACCENT, bg=INK).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(brand, text="云计算练习",
                 font=font_ui(11),
                 fg=INK_TEXT_MUTED, bg=INK).pack(side=tk.LEFT, pady=(4, 0))

        # 分隔
        tk.Frame(self, bg=INK_DIVIDER, height=1).pack(fill=tk.X, padx=20)

        # 导航
        nav_container = tk.Frame(self, bg=INK)
        nav_container.pack(fill=tk.X, padx=12, pady=(12, 0))

        for tab_id, tab_text, command in self._nav_defs:
            self._build_nav_item(nav_container, tab_id, tab_text, command)

        # 弹性空间，把就绪度环推到底部
        spacer = tk.Frame(self, bg=INK)
        spacer.pack(fill=tk.BOTH, expand=True)

        # 就绪度环（signature）
        ring_wrap = tk.Frame(self, bg=INK)
        ring_wrap.pack(pady=(0, 8))

        self.mastery_ring = MasteryRing(ring_wrap)
        self.mastery_ring.pack()

        tk.Label(self, text="练习覆盖 × 正确率",
                 font=font_ui(9),
                 fg=INK_TEXT_MUTED, bg=INK).pack(pady=(0, 4))

        # 错题数小指示
        self.wrong_indicator = tk.Label(
            self, text="",
            font=font_ui(10),
            fg=INK_TEXT_MUTED, bg=INK)
        self.wrong_indicator.pack(pady=(0, 20))

    def _build_nav_item(self, parent, tab_id: str, tab_text: str, command) -> None:
        item = tk.Frame(parent, bg=INK, cursor='hand2')
        item.pack(fill=tk.X, pady=2)

        indicator = tk.Frame(item, bg=INK, width=3)
        indicator.pack(side=tk.LEFT, fill=tk.Y)

        label = tk.Label(item, text=tab_text,
                         font=font_ui(12),
                         fg=INK_TEXT_MUTED, bg=INK,
                         cursor='hand2', anchor='w',
                         padx=14, pady=10)
        label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self._nav_refs[tab_id] = {
            'frame': item,
            'label': label,
            'indicator': indicator,
            'command': command,
        }

        for w in [item, label]:
            w.bind('<Button-1>', lambda e, t=tab_id: self._handle_nav_click(t))
            w.bind('<Enter>', lambda e, t=tab_id: self._on_nav_hover(t))
            w.bind('<Leave>', lambda e, t=tab_id: self._on_nav_leave(t))

    def _handle_nav_click(self, tab_id: str) -> None:
        """处理导航项点击：更新高亮、执行命令、触发外部回调。"""
        self.set_active_nav(tab_id)
        ref = self._nav_refs.get(tab_id)
        if ref and ref['command']:
            ref['command']()
        if self._on_nav_clicked:
            self._on_nav_clicked(tab_id)

    def _on_nav_hover(self, tab_id: str) -> None:
        """悬停非活动项时临时高亮。"""
        if tab_id == self._active_nav:
            return
        ref = self._nav_refs.get(tab_id)
        if ref:
            ref['label'].configure(fg=INK_TEXT)

    def _on_nav_leave(self, tab_id: str) -> None:
        """离开非活动项时恢复默认颜色。"""
        if tab_id == self._active_nav:
            return
        ref = self._nav_refs.get(tab_id)
        if ref:
            ref['label'].configure(fg=INK_TEXT_MUTED)

    def set_active_nav(self, tab_id: str) -> None:
        """设置当前活动导航项并更新高亮。"""
        self._active_nav = tab_id
        self._update_nav_highlight()

    def _update_nav_highlight(self) -> None:
        for tab_id, ref in self._nav_refs.items():
            if tab_id == self._active_nav:
                ref['label'].configure(fg=ACCENT, font=font_ui_semibold(12))
                ref['indicator'].configure(bg=ACCENT)
            else:
                ref['label'].configure(fg=INK_TEXT_MUTED, font=font_ui(12))
                ref['indicator'].configure(bg=INK)

    def set_mastery(self, mastery: float) -> None:
        """更新就绪度环。"""
        if self.mastery_ring is not None:
            self.mastery_ring.set_mastery(mastery)

    def set_wrong_indicator(self, text: str, fg=None) -> None:
        """更新错题指示器文本与颜色。"""
        if self.wrong_indicator is not None:
            kwargs = {'text': text}
            if fg is not None:
                kwargs['fg'] = fg
            self.wrong_indicator.configure(**kwargs)
