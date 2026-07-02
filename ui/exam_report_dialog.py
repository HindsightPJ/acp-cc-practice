"""考试成绩报告对话框。"""

import tkinter as tk
from datetime import datetime
from typing import Dict, Any, Optional, Callable

from .theme import Theme, font_ui, font_ui_semibold, font_mono, create_primary_button, create_normal_button, create_card

theme = Theme()


class ExamReportDialog:
    """考试成绩报告对话框。"""

    def __init__(
        self,
        parent,
        report: Dict[str, Any],
        on_add_wrong: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        """初始化对话框。

        Args:
            parent: 父窗口
            report: 考试报告数据
            on_add_wrong: 加入错题本回调
        """
        self.parent = parent
        self.report = report
        self.on_add_wrong = on_add_wrong
        self.dialog: Optional[tk.Toplevel] = None

    def show(self) -> None:
        """显示对话框。"""
        self._build_dialog()

    def _build_dialog(self) -> None:
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("考试成绩报告")
        self.dialog.geometry("600x550")
        self.dialog.configure(bg=theme.BG_PAGE)
        self.dialog.transient(self.parent.winfo_toplevel())
        self.dialog.grab_set()

        self.dialog.update_idletasks()
        width = self.dialog.winfo_width()
        height = self.dialog.winfo_height()
        x = (self.dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (height // 2)
        self.dialog.geometry(f"{width}x{height}+{x}+{y}")

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
        acc_color = (
            theme.GREEN if accuracy >= 80 else (theme.YELLOW if accuracy >= 60 else theme.RED)
        )

        score_card, score_inner = create_card(self.dialog, inner_padx=24, inner_pady=20)
        score_card.pack(fill=tk.X, padx=20, pady=16)

        acc_frame = tk.Frame(score_inner, bg=theme.BG_CARD)
        acc_frame.pack(fill=tk.X, pady=(0, 16))

        tk.Label(
            acc_frame, text=f"{accuracy:.1f}%", font=font_mono(32), fg=acc_color, bg=theme.BG_CARD
        ).pack(side=tk.LEFT, padx=(0, 12))

        tk.Label(
            acc_frame, text="正确率", font=font_ui(12), fg=theme.TEXT_MUTED, bg=theme.BG_CARD
        ).pack(side=tk.LEFT)

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

            tk.Label(
                w_inner,
                text=f"错题 ({len(self.report['wrong_questions'])} 题)",
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
                content_preview = q.content[:50]
                wrong_text.insert(tk.END, f"第 {q.number} 题: {content_preview}...\n\n")

            wrong_text.config(state=tk.DISABLED)

            add_wrong_btn = create_primary_button(
                w_inner,
                text="加入错题本",
                command=self._on_add_wrong_click,
                bg_color=theme.RED,
                active_bg="#dc2626",
                padx=16,
                pady=5,
            )
            add_wrong_btn.pack(pady=(10, 0))

        close_btn = create_normal_button(
            self.dialog,
            text="关闭",
            command=self.dialog.destroy,
            width=12,
            padx=16,
            pady=6,
        )
        close_btn.pack(pady=(0, 20))

    def _on_add_wrong_click(self) -> None:
        """处理加入错题本按钮点击。"""
        if self.on_add_wrong:
            self.on_add_wrong(self.report)
