"""动态属性反白渲染回归测试（P9-2）。

背景缺陷：repolish() 只刷容器不刷后代，祖先 state 属性驱动的后代规则
（QFrame[state=selected] QLabel 反白）在状态切换后不重算，子标签停留在
上一次全量样式——浅色首选黑字、换肤往返后再换选项白字/黑字全冻结。

QSS 颜色不落 palette，只能渲染取像素验证（offscreen，conftest 已配）。
判据（与主题 Token 强耦合，theme.Token 变更需同步）：
- 浅色选中：行底 ACCENT #002fa7（min 通道 0），文字 ON_ACCENT #ffffff
- 浅色未选：行底 BG #f2f0eb（min 通道 235），文字 INK #111111
"""

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from ui.answer_sheet import AnswerSheet
from ui.option_row import OptionRow
from ui.theme import apply_qss, set_theme_mode

_BRIGHT = 200  # ON_ACCENT #ffffff 与浅底 #f2f0eb 的 min 通道均 > 200
_DARK = 60  # INK #111111 与 ACCENT #002fa7 的 min 通道均 < 60


def _region_counts(widget, region) -> tuple[int, int]:
    """渲染 widget 并统计 region 内（亮核像素数, 暗核像素数）。"""
    img = widget.grab().toImage()
    bright = dark = 0
    for y in range(region.top(), region.bottom() + 1):
        for x in range(region.left(), region.right() + 1):
            c = img.pixelColor(x, y)
            v = min(c.red(), c.green(), c.blue())
            if v > _BRIGHT:
                bright += 1
            elif v < _DARK:
                dark += 1
    return bright, dark


def _shown(qtbot, widget):
    # 挪离 (0,0)：离屏光标固定在原点，压在控件上会触发 :hover 污染底色
    widget.move(600, 400)
    widget.show()
    qtbot.wait(50)  # 离屏平台完成布局/首刷
    return widget


@pytest.fixture(autouse=True)
def _light_qss_and_restore(qapp: QApplication):
    """每个用例固定浅色全量样式，结束恢复浅色避免污染后续用例。

    与运行时路径一致：set_theme_mode（同步 Token 单例）+ apply_qss（重渲染）。
    """
    set_theme_mode("light")
    apply_qss(qapp, "light")
    yield
    set_theme_mode("light")
    apply_qss(qapp, "light")


def test_selected_text_is_white_on_accent(qtbot):
    """浅色首选即反白：修复前 repolish 不刷子标签，文字停留 INK 黑。"""
    row = OptionRow("A")
    row.update_text("选中后文字应变白")
    _shown(qtbot, row)
    row.set_selected(True)
    bright, _dark = _region_counts(row, row.text_label.geometry())
    assert bright > 0, "选中行文字未渲染为反白（ON_ACCENT）"


def test_selection_change_updates_labels_after_theme_roundtrip(qtbot, qapp):
    """用户复现路径：换肤往返后切换选项，旧行退黑、新行反白。"""
    row_a = OptionRow("A")
    row_b = OptionRow("B")
    row_a.update_text("旧选中项")
    row_b.update_text("新选中项")
    _shown(qtbot, row_a)
    _shown(qtbot, row_b)

    row_a.set_selected(True)
    apply_qss(qapp, "dark")
    apply_qss(qapp, "light")
    row_a.set_selected(False)
    row_b.set_selected(True)

    bright_a, dark_a = _region_counts(row_a, row_a.text_label.geometry())
    bright_b, _dark_b = _region_counts(row_b, row_b.text_label.geometry())
    # 旧行底已回浅 BG（min 通道 235）：文字退黑则必有暗核像素
    assert dark_a > 0, "旧行取消选中后文字未退回 INK 黑"
    assert bright_b > 0, "新选中行文字未渲染为反白（ON_ACCENT）"


def test_dep_row_now_highlight_applies_without_full_restyle(qtbot):
    """答题卡"进行中"行蓝色高亮即时生效（修复前 set_state 从未 repolish）。"""
    sheet = AnswerSheet()
    qtbot.addWidget(sheet)
    sheet.build_rows(3)
    _shown(qtbot, sheet)

    sheet.update_row(0, "now")
    row = sheet._rows[0]
    img = row.grab().toImage()
    margin = img.pixelColor(2, img.height() // 2)  # 行左内边距纯底色区
    assert margin.blue() > 120 and margin.red() < 80, (
        f"now 行底色未变 ACCENT，实际 RGB=({margin.red()},{margin.green()},{margin.blue()})"
    )

    sheet.update_row(0, "")
    img = row.grab().toImage()
    margin = img.pixelColor(2, img.height() // 2)
    assert margin.red() > 200 and margin.green() > 200, (
        f"退出 now 后行底色未回 BG，实际 RGB=({margin.red()},{margin.green()},{margin.blue()})"
    )


# ---------------------------------------------------------------------------
# P9-2 状态矩阵：容器 state + 后代规则是 repolish 缺陷的唯一脆弱类，
# OptionRow 4 态 × depRow 4 态 × 双主题全量扫描，禁止单点补测。
# ---------------------------------------------------------------------------


def _has_core(widget, region, hex_color: str, tol: int = 2) -> bool:
    """region 内是否存在接近 hex_color 的核心像素（含抗锯齿容差）。"""
    want = QColor(hex_color)
    img = widget.grab().toImage()
    for y in range(region.top(), region.bottom() + 1):
        for x in range(region.left(), region.right() + 1):
            c = img.pixelColor(x, y)
            if (
                abs(c.red() - want.red()) <= tol
                and abs(c.green() - want.green()) <= tol
                and abs(c.blue() - want.blue()) <= tol
            ):
                return True
    return False


def _apply_option_state(row: OptionRow, state: str) -> None:
    if state == "selected":
        row.set_selected(True)
    elif state == "ok":
        row.reveal_correct()
    elif state == "wrong":
        row.set_result(False, False)
    else:
        row.reset()


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize(
    "state,token",
    [
        ("idle", "INK"),
        ("selected", "ON_ACCENT"),
        ("ok", "INK"),
        ("wrong", "INK3"),
    ],
)
def test_option_row_text_color_matrix(qtbot, qapp, mode, state, token):
    """选项行文字颜色随 state 与主题即时重算（后代规则必须被 repolish 刷到）。

    文本用全块字符渲染纯色矩形：14px 中文笔画太细，抗锯齿使字形核心
    到不了纯色，精确比对必须用实心块。
    """
    from ui.theme import theme

    set_theme_mode(mode)
    apply_qss(qapp, mode)
    row = OptionRow("A")
    row.update_text("██████")
    _shown(qtbot, row)
    _apply_option_state(row, state)
    expected = getattr(theme, token)
    assert _has_core(row, row.text_label.geometry(), expected), (
        f"{mode}/{state} 文字核心色未命中 {token}={expected}"
    )


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("state", ["", "done", "now", "miss"])
def test_dep_row_bg_matrix(qtbot, qapp, mode, state):
    """答题卡行底色随 state 与主题即时重算（set_state 必须触发 repolish）。"""
    from ui.theme import theme

    set_theme_mode(mode)
    apply_qss(qapp, mode)
    sheet = AnswerSheet()
    qtbot.addWidget(sheet)
    sheet.build_rows(2)
    _shown(qtbot, sheet)
    sheet.update_row(1, state)
    row = sheet._rows[1]
    img = row.grab().toImage()
    c = img.pixelColor(2, img.height() // 2)
    expected = QColor(theme.ACCENT if state == "now" else theme.BG)
    assert (
        abs(c.red() - expected.red()) <= 2
        and abs(c.green() - expected.green()) <= 2
        and abs(c.blue() - expected.blue()) <= 2
    ), f"{mode}/{state or 'idle'} 行底色未命中，实际 RGB=({c.red()},{c.green()},{c.blue()})"
