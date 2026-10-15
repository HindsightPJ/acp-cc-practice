"""考试成绩报告对话框（QDialog 版，F 方案去卡片化）。

F 语言呈现：4px 规则线分段 + 正确率大号数字（替代 tkinter 版 MasteryRing
环形装饰，F 方案无装饰图形）+ 通过/未通过判定（ACCENT 蓝 / INK3 灰，
F 方案单强调色无红绿）+ 错题逐题回顾 + 加入错题本（防重复点击）。

P9-3：错题清单由 QPlainTextEdit 改为上一题/下一题逐题回顾——
- 文本框可全选复制且原先截断前 10 条；QLabel 默认不可选中，无复制入口
- 复用 OptionRow 状态语言：已选 ✗ 反白 / 正确答案 ✓ 蓝标，与练习页一致
"""

from datetime import datetime
from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from models import Question
from .base_dialog import BaseDialog
from .option_row import OptionRow
from .question_detail_card import type_label

# 通过线（沿袭 tkinter 版语义）
_PASS_LINE = 60.0


class ExamReportDialog(BaseDialog):
    """考试成绩报告对话框。

    Args:
        parent: 父窗口
        report: QuizEngine.get_exam_report() 报告 dict
        on_add_wrong: 加入错题本回调（参数 report，返回本次新增数量）
    """

    def __init__(
        self,
        parent: QWidget | None,
        report: dict[str, Any],
        on_add_wrong: Callable[[dict[str, Any]], int] | None = None,
    ) -> None:
        super().__init__(parent, title="考试成绩报告", width=620, height=660)
        self.report = report
        self.on_add_wrong = on_add_wrong
        self._wrong_added = False
        # 错题明细：(题目, 用户作答)。旧结构（仅 wrong_questions）降级为无作答回顾
        self._wrong_records: list[tuple[Question, str]] = [
            (w["question"], str(w.get("selected", ""))) for w in (report.get("wrong_records") or [])
        ] or [(q, "") for q in (report.get("wrong_questions") or [])]
        self._wrong_index = 0
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
        stamp.setObjectName("qMeta")
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
        verdict.setObjectName("expResult")  # QSS 为 ID 选择器
        verdict.setProperty("verdict", "ok" if acc >= _PASS_LINE else "wrong")
        sub = QLabel(f"共 {self.report.get('total_questions', 0)} 题")
        sub.setObjectName("qMeta")
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

        # ── 错题逐题回顾（有错题才显示）──
        if self._wrong_records:
            wrong_head = QLabel(f"错题回顾（{len(self._wrong_records)} 题）")
            wrong_head.setObjectName("qMeta")
            v.addWidget(wrong_head)

            nav_row = QFrame()
            nh = QHBoxLayout(nav_row)
            nh.setContentsMargins(0, 0, 0, 0)
            nh.setSpacing(10)
            self._prev_btn = QPushButton("← 上一题")
            self._prev_btn.setProperty("actBtn", True)
            self._prev_btn.clicked.connect(self._go_prev_wrong)
            self._nav_pos = QLabel()
            self._nav_pos.setObjectName("qMeta")
            self._next_btn = QPushButton("下一题 →")
            self._next_btn.setProperty("actBtn", True)
            self._next_btn.clicked.connect(self._go_next_wrong)
            nh.addWidget(self._prev_btn)
            nh.addWidget(self._nav_pos)
            nh.addStretch(1)
            nh.addWidget(self._next_btn)
            v.addWidget(nav_row)

            # 题面 + 选项行放滚动区：长题干 + 6 选项不撑爆对话框
            self._detail_scroll = QScrollArea()
            self._detail_scroll.setWidgetResizable(True)
            self._detail_scroll.setFrameShape(QFrame.Shape.NoFrame)
            v.addWidget(self._detail_scroll, 1)

            self._add_wrong_btn = QPushButton("加入错题本")
            self._add_wrong_btn.setProperty("actBtn", True)
            self._add_wrong_btn.clicked.connect(self._on_add_wrong_click)
            v.addWidget(self._add_wrong_btn)

            self._show_wrong_record()

        # ── 关闭 ──
        line = QFrame()
        line.setObjectName("qline")
        v.addWidget(line)
        close_btn = QPushButton("关闭")
        close_btn.setObjectName("goBtn")
        close_btn.clicked.connect(self.accept)
        v.addWidget(close_btn)

    # ------------------------------------------------------------ 错题回顾
    def _go_prev_wrong(self) -> None:
        if self._wrong_index > 0:
            self._wrong_index -= 1
            self._show_wrong_record()

    def _go_next_wrong(self) -> None:
        if self._wrong_index < len(self._wrong_records) - 1:
            self._wrong_index += 1
            self._show_wrong_record()

    def _show_wrong_record(self) -> None:
        """渲染当前错题：题号/题型 meta + 题面 + 选项逐字母判定行。"""
        total = len(self._wrong_records)
        question, selected = self._wrong_records[self._wrong_index]
        self._nav_pos.setText(f"错题 {self._wrong_index + 1} / {total}")
        self._prev_btn.setEnabled(self._wrong_index > 0)
        self._next_btn.setEnabled(self._wrong_index < total - 1)

        body = QWidget()
        bv = QVBoxLayout(body)
        bv.setContentsMargins(0, 4, 0, 4)
        bv.setSpacing(0)

        # 题号 + 题型 meta（多选题 ACCENT 变色提醒，与练习页题头一致）
        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(0, 0, 0, 0)
        meta_row.setSpacing(10)
        no_lbl = QLabel(f"第 {question.number} 题")
        no_lbl.setObjectName("qMeta")
        type_lbl = QLabel(type_label(question.type))
        type_lbl.setObjectName("qMeta")
        if question.type == "multiple":
            type_lbl.setProperty("qType", "multiple")
        meta_row.addWidget(no_lbl)
        meta_row.addWidget(type_lbl)
        meta_row.addStretch(1)
        bv.addLayout(meta_row)

        stem = QLabel(question.content)
        stem.setProperty("optText", True)
        stem.setWordWrap(True)
        bv.addWidget(stem)
        top_line = QFrame()
        top_line.setObjectName("opts")
        bv.addWidget(top_line)

        # 逐字母四象限判定（与 QuestionDetailCard.set_option_result 同语义）：
        # 已选 ✓ / 未选 ✓ / 已选 ✗ / — 未选
        picked = set(selected.upper())
        correct = set(question.answer.upper())
        for opt in question.options:
            card = OptionRow(opt.letter)
            card.update_text(opt.text)
            card.setCursor(Qt.CursorShape.ArrowCursor)  # 只读回顾，去手型
            card.set_result(opt.letter in correct, opt.letter in picked)
            bv.addWidget(card)

        self._detail_scroll.setWidget(body)

    def _on_add_wrong_click(self) -> None:
        """加入错题本（成功后禁用，防重复点击）。"""
        if self.on_add_wrong is None or self._wrong_added:
            return
        added = self.on_add_wrong(self.report)
        if added > 0:
            self._wrong_added = True
            self._add_wrong_btn.setEnabled(False)
            self._add_wrong_btn.setText("已加入错题本")
