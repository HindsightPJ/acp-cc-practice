"""answer_sheet.py 单元测试（PySide6 版）。

覆盖 M9/M12/M22 审核修复：
- M9: _DepRow.set_state 状态未变化时短路 repolish（868 题全库队列下
  每次翻题约 3500 次 setProperty + repolish，未变化行占 99% 以上）
- M12: StatColumn.update_value 公开方法（替代调用方解包 _blocks 私有结构）
- M22: 真实鼠标点击链路（_DepRow.mousePressEvent → clicked → row_clicked）
"""

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from ui.answer_sheet import AnswerSheet, StatColumn, _DepRow

pytestmark = pytest.mark.gui


def _left_click(widget, pos):
    # [VERSION_LOCKED] PySide6 6.12：5 参便捷构造已弃用，用带 scene/global
    # 位置的 8 参构造（Qt 6 文档，2026-10 验证）
    return QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(pos),
        QPointF(pos),
        QPointF(pos),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


@pytest.fixture
def dep_row(qtbot):
    row = _DepRow(0)
    qtbot.addWidget(row)
    return row


# ---------- M9: set_state 未变化短路 ----------


def test_set_state_unchanged_short_circuits_repolish(dep_row, monkeypatch):
    """M9: 状态未变化时不触发 repolish（递归 unpolish/polish 整棵子树）。"""
    import ui.answer_sheet as answer_sheet_module

    polish_calls: list[int] = []
    monkeypatch.setattr(answer_sheet_module, "repolish", lambda widget: polish_calls.append(1))

    dep_row.set_state("done")
    assert len(polish_calls) == 1
    assert dep_row.lbl_st.text() == "已答"

    dep_row.set_state("done")  # 重复同状态 → 短路
    assert len(polish_calls) == 1

    dep_row.set_state("now")  # 状态变化 → 刷新
    assert len(polish_calls) == 2
    assert dep_row.lbl_st.text() == "进行中"


def test_set_state_empty_resets_to_pending(dep_row):
    """state="" 回落到待答态（QSS state 属性置空）。"""
    dep_row.set_state("done")
    dep_row.set_state("")
    assert dep_row.lbl_st.text() == "待答"
    assert dep_row.property("state") is None


# ---------- M12: StatColumn.update_value 公开接口 ----------


def test_stat_column_update_value_public_api(qtbot):
    """M12: 倒计时秒级刷新走 update_value 公开方法，不触碰 _blocks 私有结构。"""
    col = StatColumn()
    qtbot.addWidget(col)
    col.set_stats([("剩余时间", "29:59", ""), ("已答", "0/50", ""), ("标记", "0", "题")])

    col.update_value(0, "29:58")
    assert col._blocks[0][1].text() == "29:58"

    col.update_value(99, "out-of-range")  # 越界索引静默无操作
    assert col._blocks[0][1].text() == "29:58"


# ---------- M22: 真实鼠标点击链路 ----------


def test_dep_row_mouse_click_emits_queue_index(qtbot, dep_row):
    """M22: 真实 mousePressEvent 链路发出队列索引（此前测试都直接调处理方法，
    点击链路从未被端到端验证）。"""
    signals: list[int] = []
    dep_row.clicked.connect(signals.append)

    QApplication.sendEvent(dep_row, _left_click(dep_row, dep_row.rect().center()))

    assert signals == [0]


def test_answer_sheet_row_clicked_end_to_end(qtbot):
    """M22: AnswerSheet 行点击 → row_clicked 信号值 = 队列索引。"""
    sheet = AnswerSheet()
    qtbot.addWidget(sheet)
    sheet.build_rows(3)

    received: list[int] = []
    sheet.row_clicked.connect(received.append)

    QApplication.sendEvent(
        sheet._rows[2], _left_click(sheet._rows[2], sheet._rows[2].rect().center())
    )

    assert received == [2]
