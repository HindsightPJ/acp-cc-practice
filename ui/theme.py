"""F 方案「时刻表」设计基座：语义 Token + build_qss 全局 QSS（desktop_python.md §6）。

单一取色源（§6.1）：
- Token 层：LIGHT_TOKENS / DARK_TOKENS 同一组语义名两份映射，权威值来自
  docs/design/proposal_F_transit.html（浅）、proposal_F_transit_dark.html（深）
  与 proposal_F_titlebar_win10.html 情况③；
- 生成层：build_qss() 将 Token 展开为全局 QSS，控件代码只写语义
  objectName/动态属性选择器，禁止散写颜色；
- 换肤：set_theme_mode() 后由应用层 setStyleSheet(build_qss()) 重新应用，
  控件零缓存颜色。QSS 无 transition/box-shadow/letter-spacing（Qt 能力边界，
  设计基线已接受，见 TASK_PLAN §1）。

字体（全部 Win10 系统自带，禁止打包字体文件）：Bahnschrift（西文/数字/
大号标题）+ Microsoft YaHei UI（中文）+ Cascadia Mono（等宽数字）；
经 QFontDatabase 真实检测生成 fallback 链（Bahnschrift 缺失 → Segoe UI →
Microsoft YaHei UI）。QFontDatabase 查询需 QApplication 已创建，故懒加载缓存。
"""

from __future__ import annotations

from dataclasses import dataclass, fields
import logging

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QWidget

logger = logging.getLogger(__name__)

THEME_LIGHT = "light"
THEME_DARK = "dark"
THEME_MODES = frozenset({THEME_LIGHT, THEME_DARK})


@dataclass
class Theme:
    """语义 Token 集（字段名即 Token 名，浅色为默认值）。

    用法：控件代码原则上不直接读 Token（颜色走 QSS 类名）；
    少数程序化着色场景（如自绘）经 theme.XXX 访问，禁散写十六进制。
    """

    # 基底与文字（时刻表纸面 / 夜行板）
    BG: str = "#f2f0eb"
    INK: str = "#111111"
    INK2: str = "#6a6a66"
    INK3: str = "#b6b4ac"

    # 规则线：LINE = 一般分隔线；LINE_SOFT = 弱分隔（列/行）；粗规则线 = INK 4px
    LINE: str = "#dcd9d0"
    LINE_SOFT: str = "#dcd9d0"
    TITLEBAR_LINE: str = "#dcd9d0"  # 标题栏底缘（深色 mockup 用更暗的 #1c1b20）

    # 强调色：IKB 克莱因蓝（浅）/ 提亮克莱因蓝（深）
    ACCENT: str = "#002fa7"
    ACCENT_DEEP: str = "#001d80"  # go 按钮按下/悬停加深
    ACCENT_TINT: str = "#e8ecf9"  # hover 浅底
    ON_ACCENT: str = "#ffffff"
    ON_ACCENT_MUTED: str = "#b9c6ef"  # 反白行内的次级文字（已选标记/kbd）

    # 导航激活行的计数灰（黑底反白行内）
    NAV_ACTIVE_MUTED: str = "#9a9a94"

    # 面板（输入框 / 白纸卡，深色为 #1a1a1f 暖炭面板）
    PANEL: str = "#ffffff"
    PANEL_BORDER: str = "#c8c5bb"

    # 关闭按钮 hover（Windows 惯例红，双主题一致）
    CLOSE_RED: str = "#e81123"


# 深色映射（夜行时刻表）：底暖炭非纯黑、4px 粗规则线翻米白、克莱因蓝提亮
_DARK_TOKENS: dict[str, str] = {
    "BG": "#141417",
    "INK": "#f0efe9",
    "INK2": "#9a9890",
    "INK3": "#57554e",
    "LINE": "#2b2a30",
    "LINE_SOFT": "#222126",
    "TITLEBAR_LINE": "#1c1b20",
    "ACCENT": "#5272ff",
    "ACCENT_DEEP": "#3451d4",
    "ACCENT_TINT": "#1d2338",
    "ON_ACCENT": "#ffffff",
    "ON_ACCENT_MUTED": "#cdd6ff",
    "NAV_ACTIVE_MUTED": "#6a6962",
    "PANEL": "#1a1a1f",
    "PANEL_BORDER": "#26252b",
    "CLOSE_RED": "#e81123",
}

# 模块级单例：所有 UI 组件共享同一 Theme 实例
theme = Theme()

# 当前主题模式（"light" / "dark"），set_theme_mode 维护。
# 权威源是 AppState.theme_mode（随进度持久化）；本模块全局仅是应用内缓存，
# 供 current_theme_mode() 快速读取——单实例桌面应用下二者同步，测试若直接
# 改动本变量须自行还原，否则会污染后续用例
_current_mode: str = THEME_LIGHT

# 浅色快照（dataclass 默认值），供 set_theme_mode 切回浅色使用
_LIGHT_TOKENS: dict[str, str] = {f.name: getattr(theme, f.name) for f in fields(theme)}

# 模块导入即完成的静态校验：两套 Token 字段名必须完全一致（§6.1 同名映射）
if set(_LIGHT_TOKENS) != set(_DARK_TOKENS):
    raise RuntimeError(
        f"双主题 Token 字段名不一致: light={sorted(_LIGHT_TOKENS)} dark={sorted(_DARK_TOKENS)}"
    )


def current_theme_mode() -> str:
    """返回当前主题模式（"light" / "dark"）。"""
    return _current_mode


def set_theme_mode(mode: str) -> str:
    """切换主题：原地更新 theme 单例字段。

    调用方负责随后 QApplication.setStyleSheet(build_qss()) 重应用全局 QSS。
    非法值 fail-safe 回退浅色并记 warning（不静默）。

    Args:
        mode: "light" / "dark"（大小写不敏感）

    Returns:
        实际生效的模式名
    """
    global _current_mode
    normalized = str(mode).strip().lower()
    if normalized not in THEME_MODES:
        logger.warning("非法主题模式 %r，回退 %s", mode, THEME_LIGHT)
        normalized = THEME_LIGHT
    tokens = _DARK_TOKENS if normalized == THEME_DARK else _LIGHT_TOKENS
    for name, value in tokens.items():
        setattr(theme, name, value)
    _current_mode = normalized
    return normalized


# ---------------------------------------------------------------------------
# 字体检测（懒加载，需 QApplication 已创建）
# ---------------------------------------------------------------------------

_FONT_CACHE: tuple[str, str, str] | None = None


def _detect_fonts() -> tuple[str, str, str]:
    """检测系统字体，返回 (sans, cjk, mono) 字体族名。

    fallback 链（TASK_PLAN §6.3）：Bahnschrift 缺失（Win10 早期版本）→
    Segoe UI → Microsoft YaHei UI；等宽 Cascadia Mono → Consolas。
    结果进程内缓存（字体集运行期不变）。
    """
    global _FONT_CACHE
    if _FONT_CACHE is None:
        installed = set(QFontDatabase.families())

        def _pick(candidates: tuple[str, ...], fallback: str) -> str:
            for name in candidates:
                if name in installed:
                    return name
            return fallback

        _FONT_CACHE = (
            _pick(("Bahnschrift", "Segoe UI"), "Microsoft YaHei UI"),
            _pick(("Microsoft YaHei UI", "Microsoft YaHei"), "Microsoft YaHei"),
            _pick(("Cascadia Mono", "Cascadia Code", "Consolas"), "Courier New"),
        )
        logger.info("字体栈 sans=%s cjk=%s mono=%s", *_FONT_CACHE)
    return _FONT_CACHE


# ---------------------------------------------------------------------------
# QSS 生成（%-格式化：QSS 含大量字面大括号，f-string/format 不适用）
# ---------------------------------------------------------------------------

_QSS_TEMPLATE = """
/* ===== F 方案「时刻表」全局 QSS（由 Token 生成，禁手改颜色字面量）===== */
* { outline: none; }

QWidget {
    background-color: %(BG)s;
    color: %(INK)s;
    font-family: "%(SANS)s", "%(CJK)s";
    font-size: 13px;
}
QLabel { background: transparent; }

/* ── 窗口根（frameless 后的 1px 桌面分界线）── */
QFrame#windowRoot { border: 1px solid %(PANEL_BORDER)s; }

/* ── Frameless 标题栏（情况③：44px 站牌条）── */
QFrame#titlebar { background: %(BG)s; border-bottom: 1px solid %(TITLEBAR_LINE)s; }
QLabel#tbBrand { font-family: "%(SANS)s"; font-weight: 600; font-size: 15px; color: %(INK)s; }
QPushButton[role="win"] {
    background: transparent; border: none; color: %(INK2)s;
    font-size: 11px; width: 50px;
}
QPushButton[role="win"]:hover { background: %(ACCENT_TINT)s; color: %(INK)s; }
QPushButton[role="close"]:hover { background: %(CLOSE_RED)s; color: %(ON_ACCENT)s; }

/* ── 授权入口（head 右侧 pill 按钮，试用态可点开注册码对话框）── */
QPushButton#licenseBtn {
    background: transparent; border: 1px solid %(LINE)s; color: %(INK2)s;
    padding: 7px 16px; font-size: 12px;
}
QPushButton#licenseBtn:hover {
    border-color: %(ACCENT)s; color: %(ACCENT)s; background: %(ACCENT_TINT)s;
}
QPushButton#licenseBtn:disabled {
    color: %(INK3)s; border-color: %(LINE)s; background: transparent;
}

/* ── 站牌头（4px 粗规则线压底）── */
QFrame#head { background: %(BG)s; border-bottom: 4px solid %(INK)s; }
QLabel#brand { font-family: "%(SANS)s"; font-weight: 600; font-size: 34px; color: %(INK)s; }
QLabel#subTitle { color: %(INK2)s; font-size: 12px; }
QLabel#clockTime { font-family: "%(MONO)s"; font-weight: 600; font-size: 30px; color: %(INK)s; }
QLabel#clockDate { color: %(INK2)s; font-size: 10px; }

/* ── board-nav（时刻表导航行：激活 = 黑底反白）── */
/* 注意：Qt QSS 的祖先伪类（:checked QLabel）会错误命中所有兄弟行
   （实测 6.12 复现），故反白子标签用 navActive 动态属性驱动，
   :checked 只用于按钮自身背景。 */
QFrame#boardNav { border-bottom: 1px solid %(INK)s; }
QPushButton[navRow="true"] {
    background: transparent; border: none; border-right: 1px solid %(LINE_SOFT)s;
    text-align: left; padding: 10px 18px; color: %(INK2)s; font-size: 13px;
}
QPushButton[navRow="true"]:hover { background: %(ACCENT_TINT)s; }
QPushButton[navRow="true"]:checked { background: %(INK)s; }
QPushButton[navRow="true"] QLabel { background: transparent; }
QLabel[navNo] { font-family: "%(SANS)s"; font-weight: 600; font-size: 22px; color: %(INK3)s; }
QLabel[navNm] { font-size: 13px; color: %(INK2)s; }
QLabel[navCnt] { font-family: "%(MONO)s"; font-size: 12px; color: %(INK3)s; }
QLabel[navNo][navActive="true"] { color: %(BG)s; }
QLabel[navNm][navActive="true"] { color: %(BG)s; }
QLabel[navCnt][navActive="true"] { color: %(NAV_ACTIVE_MUTED)s; }

/* ── 题区（可见网格左列）── */
QFrame#qcol { border-right: 1px solid %(LINE_SOFT)s; }
QFrame#qline { border-bottom: 1px solid %(INK)s; }
QLabel#qBig { font-family: "%(SANS)s"; font-weight: 600; font-size: 54px; color: %(INK)s; }
QLabel#qMeta { color: %(INK2)s; font-size: 11px; }
QLabel#qMeta[qType="multiple"] { color: %(ACCENT)s; font-weight: 600; }
QLabel#stem { color: %(INK)s; font-size: 16px; }

/* ── 选项 = 发牌板行 ── */
QFrame#opts { border-top: 1px solid %(INK)s; }
QFrame[optRow="true"] { background: %(BG)s; border-bottom: 1px solid %(LINE)s; }
QFrame[optRow="true"]:hover { background: %(ACCENT_TINT)s; }
QFrame[optRow="true"] QLabel { background: transparent; }
QLabel[optKey] { font-family: "%(SANS)s"; font-weight: 600; font-size: 15px; color: %(INK2)s; }
QLabel[optText] { font-size: 14px; color: %(INK)s; }
QLabel[optMark] { font-family: "%(MONO)s"; font-size: 11px; color: %(INK3)s; }
/* 状态规则须置于 :hover 之后（同优先级后写胜出），选中行 hover 保持反白 */
QFrame[optRow="true"][state="selected"] { background: %(ACCENT)s; }
QFrame[optRow="true"][state="selected"]:hover { background: %(ACCENT)s; }
QFrame[optRow="true"][state="selected"] QLabel { color: %(ON_ACCENT)s; }
QFrame[optRow="true"][state="selected"] QLabel[optMark] { color: %(ON_ACCENT_MUTED)s; }
QFrame[optRow="true"][state="ok"] QLabel[optKey] { color: %(ACCENT)s; }
QFrame[optRow="true"][state="ok"] QLabel[optMark] { color: %(ACCENT)s; font-weight: 600; }
QFrame[optRow="true"][state="wrong"] QLabel { color: %(INK3)s; }
QFrame[optRow="true"][state="wrong"] QLabel[optMark] { color: %(INK3)s; }

/* ── 答题卡 = 发车时刻表 ── */
QFrame#acol { border-right: 1px solid %(LINE_SOFT)s; }
QLabel#acolHead {
    font-family: "%(SANS)s"; font-weight: 600; font-size: 12px; color: %(INK)s;
    padding: 12px 20px; border-bottom: 1px solid %(INK)s;
}
QFrame[depRow="true"] { background: %(BG)s; border-bottom: 1px solid %(LINE_SOFT)s; }
QFrame[depRow="true"] QLabel { background: transparent; }
QLabel[depN] { font-family: "%(MONO)s"; font-size: 13px; color: %(INK3)s; }
QLabel[depSt] { font-size: 10px; color: %(INK3)s; }
QFrame[depRow="true"][state="now"] { background: %(ACCENT)s; }
QFrame[depRow="true"][state="now"] QLabel { color: %(ON_ACCENT)s; }
QFrame[depRow="true"][state="now"] QLabel[depSt] { color: %(ON_ACCENT_MUTED)s; }
QFrame[depRow="true"][state="done"] QLabel[depN] { color: %(INK)s; }
QFrame[depRow="true"][state="done"] QLabel[depSt] { color: %(INK2)s; }
QFrame[depRow="true"][state="miss"] QLabel { color: %(INK3)s; }

/* ── 统计列 ── */
QFrame#scol { border-right: none; }
QFrame[statBlock="true"] { border-bottom: 1px solid %(LINE_SOFT)s; }
QLabel[statK] { color: %(INK2)s; font-size: 10px; }
QLabel[statV] { font-family: "%(SANS)s"; font-weight: 600; font-size: 40px; color: %(INK)s; }
QLabel[statUnit] { color: %(INK2)s; font-size: 16px; }

/* ── 底部动作条（4px 粗规则线压顶）── */
/* 同 board-nav：:pressed 的后代规则不可用，按下反馈只变按钮自身底色 */
QFrame#actionsBar { border-top: 4px solid %(INK)s; }
QPushButton[actBtn="true"] {
    background: transparent; border: none; border-right: 1px solid %(LINE_SOFT)s;
    color: %(INK)s; font-size: 13px; padding: 13px;
}
QPushButton[actBtn="true"]:hover { background: %(ACCENT_TINT)s; }
QPushButton[actBtn="true"]:pressed { background: %(LINE)s; }
QPushButton[actBtn="true"]:disabled { color: %(INK3)s; }
QPushButton[actBtn="true"] QLabel { background: transparent; }
QLabel[kbdHint] { font-family: "%(MONO)s"; font-size: 10px; color: %(INK3)s; }
QPushButton#goBtn { background: %(ACCENT)s; color: %(ON_ACCENT)s; border: none; font-size: 13px; font-weight: 600; padding: 13px; }
QPushButton#goBtn:hover { background: %(ACCENT_DEEP)s; }
QPushButton#goBtn:pressed { background: %(ACCENT_DEEP)s; }
QPushButton#goBtn:disabled { background: %(LINE)s; color: %(INK2)s; }
QPushButton#goBtn QLabel { background: transparent; color: %(ON_ACCENT)s; }
QPushButton#goBtn QLabel[kbdHint] { color: %(ON_ACCENT_MUTED)s; }
/* 随机出题等复选框入驻动作条：左侧留出站牌边距 */
QFrame#actionsBar QCheckBox { margin-left: 30px; }

/* ── modeline（底部状态行）── */
QLabel#modeline {
    font-family: "%(MONO)s"; font-size: 11px; color: %(INK3)s;
    border-top: 1px solid %(LINE_SOFT)s; padding: 4px 18px;
}

/* ── 输入控件 ── */
QLineEdit, QPlainTextEdit, QTextEdit {
    background: %(PANEL)s; color: %(INK)s;
    border: 1px solid %(LINE)s; padding: 6px 10px;
    selection-background-color: %(ACCENT)s; selection-color: %(ON_ACCENT)s;
}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus { border: 1px solid %(ACCENT)s; }
QLineEdit:disabled { color: %(INK3)s; background: %(BG)s; }

/* ── 滚动条（细轨 + 方角把手，F 无圆角语言）── */
QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: %(LINE)s; min-height: 32px; }
QScrollBar::handle:vertical:hover { background: %(INK3)s; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0; }
QScrollBar::handle:horizontal { background: %(LINE)s; min-width: 32px; }
QScrollBar::handle:horizontal:hover { background: %(INK3)s; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }

/* ── 对话框 / 提示 ── */
QDialog { background: %(BG)s; }
QMessageBox QLabel { background: transparent; font-size: 13px; }
QMessageBox QPushButton {
    background: transparent; border: 1px solid %(LINE)s; color: %(INK)s;
    min-width: 88px; padding: 8px 16px;
}
QMessageBox QPushButton:hover { background: %(ACCENT_TINT)s; }
QMessageBox QPushButton:default { background: %(ACCENT)s; color: %(ON_ACCENT)s; border-color: %(ACCENT)s; }
QToolTip { background: %(INK)s; color: %(BG)s; border: none; padding: 4px 8px; font-size: 11px; }

/* ── 基础按钮兜底（未挂语义类的按钮不再出现原生凸起样式）── */
QPushButton { background: transparent; border: none; color: %(INK)s; }
QPushButton:disabled { color: %(INK3)s; }

/* ── P4：解析块（qcol 底部，4px 规则线压顶）── */
QFrame#expBox { border-top: 4px solid %(INK)s; }
QLabel#expResult { font-family: "%(SANS)s"; font-weight: 600; font-size: 15px; color: %(INK3)s; }
QLabel#expResult[verdict="ok"] { color: %(ACCENT)s; }
QLabel#expResult[verdict="wrong"] { color: %(INK3)s; }
QLabel#expText { font-size: 13px; color: %(INK2)s; }

/* ── P4：QCheckBox（练习随机出题等，方角指示器贴 F 语言）── */
QCheckBox { color: %(INK2)s; font-size: 12px; spacing: 8px; background: transparent; }
QCheckBox::indicator { width: 13px; height: 13px; border: 1px solid %(LINE)s; background: %(PANEL)s; }
QCheckBox::indicator:hover { border-color: %(INK3)s; }
QCheckBox::indicator:checked { background: %(ACCENT)s; border-color: %(ACCENT)s; }

/* ── P4：QComboBox（考试设置，无箭头图片资源用 border 三角）── */
QComboBox { background: %(PANEL)s; color: %(INK)s; border: 1px solid %(LINE)s; padding: 6px 10px; min-width: 72px; }
QComboBox:hover { border-color: %(INK3)s; }
QComboBox:focus { border-color: %(ACCENT)s; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox::down-arrow { image: none; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid %(INK2)s; margin-right: 10px; }
QComboBox QAbstractItemView { background: %(PANEL)s; color: %(INK)s; border: 1px solid %(LINE)s; selection-background-color: %(ACCENT)s; selection-color: %(ON_ACCENT)s; outline: 0; }

/* ── P4：QTableWidget（考试历史表，方角细线网格）── */
QTableWidget { background: %(PANEL)s; color: %(INK)s; border: none; gridline-color: %(LINE_SOFT)s; selection-background-color: %(ACCENT_TINT)s; selection-color: %(INK)s; }
QHeaderView::section { background: %(BG)s; color: %(INK2)s; border: none; border-bottom: 1px solid %(INK)s; border-right: 1px solid %(LINE_SOFT)s; padding: 7px 10px; font-size: 11px; }

/* ── P4：考试题号网格（四态：未答/已答/标记/当前；均为按钮自身状态，安全）── */
QPushButton[examNav="true"] {
    background: transparent; border: 1px solid %(LINE_SOFT)s; color: %(INK3)s;
    font-family: "%(MONO)s"; font-size: 11px; padding: 4px 0; min-height: 22px;
}
QPushButton[examNav="true"]:hover { border-color: %(INK3)s; color: %(INK2)s; }
QPushButton[examNav="true"][state="answered"] { background: %(ACCENT)s; color: %(ON_ACCENT)s; border-color: %(ACCENT)s; }
QPushButton[examNav="true"][state="marked"] { background: %(ACCENT_DEEP)s; color: %(ON_ACCENT)s; border-color: %(ACCENT_DEEP)s; }
QPushButton[examNav="true"][state="current"] { background: %(INK)s; color: %(BG)s; border-color: %(INK)s; }
"""


def build_qss(mode: str | None = None) -> str:
    """由 Token 生成全局 QSS。

    Args:
        mode: None = 当前模式；否则 "light"/"dark"（非法值回退浅色）。

    Returns:
        完整全局样式表，供 QApplication.setStyleSheet() 使用。
    """
    if mode is None:
        values = {f.name: getattr(theme, f.name) for f in fields(theme)}
        normalized = _current_mode
    else:
        normalized = str(mode).strip().lower()
        if normalized not in THEME_MODES:
            logger.warning("非法主题模式 %r，回退 %s", mode, THEME_LIGHT)
            normalized = THEME_LIGHT
        values = dict(_DARK_TOKENS if normalized == THEME_DARK else _LIGHT_TOKENS)

    sans, cjk, mono = _detect_fonts()
    variables = {**values, "SANS": sans, "CJK": cjk, "MONO": mono}
    return _QSS_TEMPLATE % variables


def apply_qss(app: QApplication, mode: str | None = None) -> None:
    """把 build_qss 应用到整个应用（换肤 = 重调本函数）。"""
    app.setStyleSheet(build_qss(mode))


def repolish(widget: QWidget) -> None:
    """动态属性变更后重刷 QSS（optRow/depRow 状态切换时调用）。

    必须递归刷全部后代：祖先容器的 state 属性同时驱动后代规则
    （如 QFrame[optRow][state=selected] QLabel 的反白文字），只刷容器
    本身不会重算子标签命中的祖先属性选择器规则，换肤/切换选中后
    子标签会停留在上一次全量样式（P9-2 修复的反白文字不同步缺陷）。
    """
    style = widget.style()
    stack: list[QWidget] = [widget]
    while stack:
        w = stack.pop()
        style.unpolish(w)
        style.polish(w)
        stack.extend(w.findChildren(QWidget))


def center_window(window: QWidget) -> None:
    """把窗口居中到所在屏幕的可用区域中央（多显示器取当前 screen）。"""
    window.adjustSize()
    screen = window.screen()
    if screen is None:
        return
    geo = screen.availableGeometry()
    frame = window.frameGeometry()
    frame.moveCenter(geo.center())
    window.move(frame.topLeft())
