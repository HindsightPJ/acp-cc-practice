"""考试成绩报告对话框。"""

import tkinter as tk
from datetime import datetime
from typing import Any, Callable

from .theme import (
    theme,
    font_ui,
    font_ui_semibold,
    create_primary_button,
    create_normal_button,
    create_card,
)
from .base_dialog import BaseDialog
from .mastery_ring import MasteryRing
from .rounded import RoundedButton


class ExamReportDialog(BaseDialog):
    """考试成绩报告对话框。"""

    def __init__(
        self,
        parent: tk.Misc,
        report: dict[str, Any],
        on_add_wrong: Callable[[dict[str, Any]], int] | None = None,
    ) -> None:
        """初始化对话框。

        Args:
            parent: 父窗口
            report: 考试报告数据
            on_add_wrong: 加入错题本回调，返回本次新增数量（用于防重复点击）
        """
        super().__init__(parent, title="考试成绩报告", size="600x550")
        self.report = report
        self.on_add_wrong = on_add_wrong
        self._add_wrong_btn: RoundedButton | None = None
        self._wrong_added = False

    def show(self) -> None:
        """显示对话框。"""
        self._create_dialog()
        self._build_content()

    def _build_content(self) -> None:
        assert self.dialog is not None

        header, h_inner = create_card(self.dialog, inner_padx=24, inner_pady=20)
        header.pack(fill=tk.X, padx=20, pady=(20, 0))

        tk.Label(
            h_inner,
            text="考试成绩报告",
            font=font_ui_semibold(18),
            fg=theme.TEXT_PRIMARY,
            bg=theme.BG_CARD,
        ).pack(anchor=tk.W)

        tk.Label(
            h_inner,
            text=f"完成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            font=font_ui(10),
            fg=theme.TEXT_MUTED,
            bg=theme.BG_CARD,
        ).pack(anchor=tk.W, pady=(4, 0))

        accuracy = self.report["accuracy"]

        score_card, score_inner = create_card(self.dialog, inner_padx=24, inner_pady=20)
        score_card.pack(fill=tk.X, padx=20, pady=16)

        acc_frame = tk.Frame(score_inner, bg=theme.BG_CARD)
        acc_frame.pack(fill=tk.X, pady=(0, 16))

        # 正确率 ScoreRing（复用就绪度环的分段渐变弧，浅底配色）
        score_ring = MasteryRing(
            acc_frame,
            size=96,
            thickness=8,
            bg=theme.BG_CARD,
            label="正确率",
            center_fg=theme.TEXT_PRIMARY,
            center_muted=theme.TEXT_MUTED,
        )
        score_ring.set_mastery(accuracy / 100.0)
        score_ring.pack(side=tk.LEFT, padx=(0, 16))

        result_frame = tk.Frame(acc_frame, bg=theme.BG_CARD)
        result_frame.pack(side=tk.LEFT, fill=tk.Y, expand=True)

        verdict_text = "通过" if accuracy >= 60 else "未通过"
        verdict_color = theme.GREEN if accuracy >= 60 else theme.RED
        tk.Label(
            result_frame,
            text=verdict_text,
            font=font_ui_semibold(16),
            fg=verdict_color,
            bg=theme.BG_CARD,
        ).pack(anchor=tk.W)
        tk.Label(
            result_frame,
            text=f"正确率 {accuracy:.1f}%",
            font=font_ui(11),
            fg=theme.TEXT_SECONDARY,
            bg=theme.BG_CARD,
        ).pack(anchor=tk.W, pady=(4, 0))

        stats_grid = tk.Frame(score_inner, bg=theme.BG_CARD)
        stats_grid.pack(fill=tk.X)

        stats_data = [
            ("总题数", f"{self.report['total_questions']}", theme.TEXT_SECONDARY),
            ("正确", f"{self.report['correct']}", theme.GREEN),
            ("错误", f"{self.report['wrong']}", theme.RED),
            ("用时", self.report["time_used"], theme.ACCENT),
        ]

        for i, (label, value, color) in enumerate(stats_data):
            stat_item = tk.Frame(stats_grid, bg=theme.BG_INPUT, padx=16, pady=10)
            stat_item.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0 if i == 0 else 4, 4))

            tk.Label(
                stat_item, text=value, font=font_ui_semibold(14), fg=color, bg=theme.BG_INPUT
            ).pack()

            tk.Label(
                stat_item, text=label, font=font_ui(9), fg=theme.TEXT_MUTED, bg=theme.BG_INPUT
            ).pack(pady=(2, 0))

        if self.report["wrong_questions"]:
            wrong_card, w_inner = create_card(self.dialog, inner_padx=24, inner_pady=16)
            wrong_card.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 16))

            total_wrong = len(self.report["wrong_questions"])
            title_text = f"错题 ({total_wrong} 题)"
            if total_wrong > 10:
                # P2: 列表只渲染前 10 条，标题必须说明，否则用户以为漏渲染
                title_text += "，仅显示前 10 条"
            tk.Label(
                w_inner,
                text=title_text,
                font=font_ui_semibold(12),
                fg=theme.RED,
                bg=theme.BG_CARD,
            ).pack(anchor=tk.W, pady=(0, 8))

            wrong_list_frame = tk.Frame(w_inner, bg=theme.BG_CARD)
            wrong_list_frame.pack(fill=tk.BOTH, expand=True)

            scrollbar = tk.Scrollbar(wrong_list_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            wrong_text = tk.Text(
                wrong_list_frame,
                height=5,
                wrap=tk.WORD,
                font=font_ui(10),
                bg=theme.BG_INPUT,
                fg=theme.TEXT_SECONDARY,
                relief=tk.FLAT,
                padx=12,
                pady=8,
                yscrollcommand=scrollbar.set,
                selectbackground=theme.BG_SELECT,
                insertbackground=theme.TEXT_PRIMARY,
            )
            wrong_text.pack(fill=tk.BOTH, expand=True)
            scrollbar.config(command=wrong_text.yview)

            for q in self.report["wrong_questions"][:10]:
                # P3: 未截断的短题干不再追加省略号
                content_preview = q.content[:50] + ("..." if len(q.content) > 50 else "")
                wrong_text.insert(tk.END, f"第 {q.number} 题: {content_preview}\n\n")

            wrong_text.config(state=tk.DISABLED)

            self._add_wrong_btn = create_primary_button(
                w_inner,
                text="加入错题本",
                command=self._on_add_wrong_click,
                bg_color=theme.RED,
                active_bg=theme.RED_HOVER,
                padx=16,
                pady=5,
            )
            self._add_wrong_btn.pack(pady=(10, 0))

        close_btn = create_normal_button(
            self.dialog,
            text="关闭",
            command=self.close,
            width=12,
            padx=16,
            pady=6,
        )
        close_btn.pack(pady=(0, 20))

    def _on_add_wrong_click(self) -> None:
        """处理加入错题本按钮点击（P2: 成功加入后禁用，防重复点击）。"""
        if self.on_add_wrong is None or self._wrong_added:
            return
        added = self.on_add_wrong(self.report)
        if added > 0:
            self._wrong_added = True
            if self._add_wrong_btn is not None:
                self._add_wrong_btn.configure(state=tk.DISABLED, text="已加入错题本")
