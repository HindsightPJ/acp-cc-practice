"""考试成绩报告对话框（QDialog 版，F 方案去卡片化）。

F 语言呈现：4px 规则线分段 + 正确率大号数字（替代 tkinter 版 MasteryRing
环形装饰，F 方案无装饰图形）+ 通过/未通过判定（ACCENT 蓝 / INK3 灰，
F 方案单强调色无红绿）+ 错题清单（前 10 条）+ 加入错题本（防重复点击）。
"""

from datetime import datetime
from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from .base_dialog import BaseDialog

# 通过线（沿袭 tkinter 版语义）
_PASS_LINE = 60.0
# 错题清单最多渲染条数（超出部分由标题说明，避免用户以为漏渲染）
_MAX_WRONG_SHOWN = 10


class ExamReportDialog(BaseDialog):
    """考试成绩报告对话框。

    Args:
        parent: 父窗口
        report: QuizEngine.get_exam_report() 报告 dict
        on_add_wrong: 加入错题本回调（参数 report，返回本次新增数量）
    """

    def __init__(
        self,
        parent,
        report: dict[str, Any],
        on_add_wrong: Callable[[dict[str, Any]], int] | None = None,
    ) -> None:
        super().__init__(parent, title="考试成绩报告", width=520, height=520)
        self.report = report
        self.on_add_wrong = on_add_wrong
        self._wrong_added = False
        self._build_ui()

    def _build_ui(self) -> None:
        v = QVBoxLayout(self)
        v.setContentsMargins(28, 24, 28, 22)
        v.setSpacing(14)

        # ── 头部：4px 规则线压顶 + 大标题 + 时间 meta ──
        head = QFrame()
        head.setObjectName("expBox")
        hv = QVBoxLayout(head)
        hv.setContentsMargins(0, 14, 0, 0)
        hv.setSpacing(5)
        title = QLabel("考试成绩报告")
        title.setProperty("statV", True)  # 复用大号数字类（40px F 语言标题）
        hv.addWidget(title)
        stamp = QLabel(f"完成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        stamp.setProperty("qMeta", True)
        hv.addWidget(stamp)
        v.addWidget(head)

        # ── 分数区：正确率大数字 + 判定 ──
        score_row = QFrame()
        sh = QHBoxLayout(score_row)
        sh.setContentsMargins(0, 0, 0, 0)
        sh.setSpacing(16)
        acc = float(self.report.get("accuracy", 0))

        acc_box = QVBoxLayout()
        acc_box.setSpacing(2)
        acc_k = QLabel("正确率")
        acc_k.setProperty("statK", True)
        acc_v_row = QHBoxLayout()
        acc_v_row.setSpacing(2)
        acc_v = QLabel(f"{acc:.1f}")
        acc_v.setProperty("statV", True)
        acc_unit = QLabel("%")
        acc_unit.setProperty("statUnit", True)
        acc_v_row.addWidget(acc_v)
        acc_v_row.addWidget(acc_unit, 0, Qt.AlignmentFlag.AlignBottom)
        acc_v_row.addStretch(1)
        acc_box.addWidget(acc_k)
        acc_box.addLayout(acc_v_row)
        sh.addLayout(acc_box, 1)

        verdict_box = QVBoxLayout()
        verdict_box.setSpacing(2)
        verdict = QLabel("通过" if acc >= _PASS_LINE else "未通过")
        verdict.setProperty("expResult", True)
        verdict.setProperty("verdict", "ok" if acc >= _PASS_LINE else "wrong")
        sub = QLabel(f"共 {self.report.get('total_questions', 0)} 题")
        sub.setProperty("qMeta", True)
        verdict_box.addWidget(verdict)
        verdict_box.addWidget(sub)
        sh.addLayout(verdict_box, 1)
        v.addWidget(score_row)

        # ── 统计行：正确 / 错误 / 用时 ──
        stats_row = QFrame()
        sth = QHBoxLayout(stats_row)
        sth.setContentsMargins(0, 0, 0, 0)
        sth.setSpacing(0)
        stats_data = (
            ("正确", str(self.report.get("correct", 0)), ""),
            ("错误", str(self.report.get("wrong", 0)), ""),
            ("用时", str(self.report.get("time_used", "—")), ""),
        )
        for k_text, v_text, unit in stats_data:
            block = QFrame()
            block.setProperty("statBlock", True)
            bv = QVBoxLayout(block)
            bv.setContentsMargins(0, 8, 0, 8)
            bv.setSpacing(2)
            k_lbl = QLabel(k_text)
            k_lbl.setProperty("statK", True)
            v_lbl = QLabel(v_text)
            v_lbl.setProperty("statV", True)
            if unit:
                v_lbl.setText(f"{v_text}{unit}")
            bv.addWidget(k_lbl)
            bv.addWidget(v_lbl)
            sth.addWidget(block, 1)
        v.addWidget(stats_row)

        # ── 错题清单（有错题才显示）──
        wrong_questions = self.report.get("wrong_questions") or []
        if wrong_questions:
            total_wrong = len(wrong_questions)
            title_text = f"错题（{total_wrong} 题）"
            if total_wrong > _MAX_WRONG_SHOWN:
                title_text += f"，仅显示前 {_MAX_WRONG_SHOWN} 条"
            wrong_head = QLabel(title_text)
            wrong_head.setProperty("qMeta", True)
            v.addWidget(wrong_head)

            wrong_view = QPlainTextEdit()
            wrong_view.setReadOnly(True)
            for q in wrong_questions[:_MAX_WRONG_SHOWN]:
                content_preview = q.content[:50] + ("..." if len(q.content) > 50 else "")
                wrong_view.appendPlainText(f"第 {q.number} 题: {content_preview}")
            v.addWidget(wrong_view, 1)

            self._add_wrong_btn = QPushButton("加入错题本")
            self._add_wrong_btn.setProperty("actBtn", True)
            self._add_wrong_btn.clicked.connect(self._on_add_wrong_click)
            v.addWidget(self._add_wrong_btn)

        # ── 关闭 ──
        line = QFrame()
        line.setObjectName("qline")
        v.addWidget(line)
        close_btn = QPushButton("关闭")
        close_btn.setObjectName("goBtn")
        close_btn.clicked.connect(self.accept)
        v.addWidget(close_btn)

    def _on_add_wrong_click(self) -> None:
        """加入错题本（成功后禁用，防重复点击）。"""
        if self.on_add_wrong is None or self._wrong_added:
            return
        added = self.on_add_wrong(self.report)
        if added > 0:
            self._wrong_added = True
            self._add_wrong_btn.setEnabled(False)
            self._add_wrong_btn.setText("已加入错题本")
