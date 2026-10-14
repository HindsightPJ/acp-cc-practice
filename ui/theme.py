"""设计 Token：云霁（浅色）/ 夜航（深色）双主题 + 字体检测 + 控件工厂。

单一取色源（desktop_python.md §6.1）：
- 常量层：LIGHT/DARK 两套 Token（dataclass Theme 的字段即 Token 名）；
- 访问层：theme 单例 + 工厂函数，控件代码只引用 Token，禁散写颜色；
- 换肤：set_theme_mode() 原地更新单例字段并同步模块级常量，调用方
  重建界面后全部控件自动换色（控件禁缓存颜色值，见 TASK_PLAN D1）。

字体：正文/标题全面雅黑（Microsoft YaHei UI 真实检测 + fallback 链），
计时数字用等宽；经 _pick() 查询系统真实安装，避免被 Tkinter 静默替换。
"""

from dataclasses import dataclass, fields
import logging
import platform
import tkinter as tk
from tkinter import font as tkfont
from typing import Any, Callable

from .constants import RADIUS_BTN, RADIUS_CARD, THEME_DARK, THEME_LIGHT, THEME_MODES
from .rounded import Chip, RoundedButton, RoundedCard, Switch

logger = logging.getLogger(__name__)


def _disable_tk_autostyle() -> None:
    """禁用 ttkbootstrap 对 tk 控件的自动样式重刷。

    根因（2026-10-14 实测定位）：ttkbootstrap 1.10.1 在 import 时给所有
    tk 控件构造函数打补丁（Bootstyle.override_tk_widget_constructor），
    创建时无条件调用 update_frame_style 等 → `widget.configure(
    background=self.colors.bg)`，用当前主题背景色覆盖创建参数里显式
    传入的 bg——深色侧栏（INK）等自定义配色在创建瞬间被刷成 journal 白。
    本项目的 tk 控件颜色全部由本模块设计 Token 显式管理，自动重刷只会
    破坏设计；ttk 控件的主题化（journal + 主色覆写）走 ttk 样式系统，
    不受本禁用影响。
    """
    try:
        from ttkbootstrap.style import Bootstyle

        Bootstyle.update_tk_widget_style = staticmethod(lambda widget: None)
    except (ImportError, AttributeError) as e:
        # 无此机制（旧版/未来已修复的 ttkbootstrap）则无需禁用，留痕即可
        logger.warning("ttkbootstrap autostyle 禁用跳过: %s", e)


_disable_tk_autostyle()


def _list_system_fonts() -> set[str]:
    """查询系统真实可用字体集合。

    复用已有 Tk root（若存在），避免创建多余 root 导致 Tcl 状态冲突。
    无头环境或无 root 时返回空集合，由 fallback 兜底。
    """
    try:
        root = getattr(tk, "_default_root", None)
        if root is not None:
            return set(tkfont.families(root))
        return set()
    except tk.TclError:
        # 无头环境或 Tk root 状态异常时，返回空集合由 fallback 兜底
        return set()


_AVAILABLE_FONTS = None
_FONTS_CACHE = None


def _get_fonts() -> dict[str, str]:
    """懒加载字体配置：首次调用时检测系统字体，避免模块导入时创建 Tk root。"""
    global _FONTS_CACHE
    if _FONTS_CACHE is None:
        _FONTS_CACHE = _detect_fonts_impl()
    return _FONTS_CACHE


def _detect_fonts_impl() -> dict[str, str]:
    """全面雅黑字体栈（2026-10-14 重设计）：正文/标题统一无衬线。

    旧「纸感学术」方案的 Georgia + 宋体在屏幕小字号下衬线发虚显旧
    （用户两次改版失败的反馈），本次正文/选项/标题全面切换雅黑；
    等宽字体保留给计时器与机器码（防布局抖动）。
    通过 _list_system_fonts 真实查询，避免指定不存在的字体被
    Tkinter 静默替换为默认字体。
    """
    global _AVAILABLE_FONTS
    _AVAILABLE_FONTS = _list_system_fonts()
    system = platform.system()
    available = _AVAILABLE_FONTS

    def _pick(preferred: list[str], fallback: str) -> str:
        # 从优先级列表里挑第一个系统真实安装的字体
        for name in preferred:
            if name in available:
                return name
        return fallback

    if system == "Windows":
        ui = _pick(["Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI"], "Microsoft YaHei")
        mono = _pick(
            [
                "JetBrains Mono",
                "Fira Code",
                "Cascadia Code",
                "Cascadia Mono",
                "Consolas",
            ],
            "Consolas",
        )
    elif system == "Darwin":
        ui = _pick(["PingFang SC", "Microsoft YaHei", "Helvetica Neue"], "PingFang SC")
        mono = _pick(
            [
                "JetBrains Mono",
                "Fira Code",
                "SF Mono",
                "Menlo",
            ],
            "Menlo",
        )
    else:
        ui = _pick(
            [
                "Noto Sans CJK SC",
                "Microsoft YaHei",
                "WenQuanYi Micro Hei",
            ],
            "Noto Sans CJK SC",
        )
        mono = _pick(
            [
                "JetBrains Mono",
                "Fira Code",
                "DejaVu Sans Mono",
            ],
            "DejaVu Sans Mono",
        )

    # display 与 ui 同族：现代无衬线体系靠字重/字号分层，不靠衬线
    return {"ui": ui, "mono": mono, "display": ui}


# ---------------------------------------------------------------------------
# 设计 Token：云霁（浅色，默认）——冷灰蓝页面 + 无框白卡 + 云蓝主色
# ---------------------------------------------------------------------------
# 层次靠明度不靠边框；主色与答错红拉开语义距离（§6.1 语义距离要求）。


@dataclass
class Theme:
    """主题访问器（非 frozen：set_theme_mode 原地换肤）。

    字段名即 Token 名，浅色为默认值；深色值见 _DARK_TOKENS。
    用法：theme = Theme(); tk.Frame(parent, bg=theme.BG_PAGE)
    """

    # 页面与卡片
    BG_PAGE: str = "#eef1f6"  # 页面底——冷灰蓝，白卡浮于其上
    BG_CARD: str = "#ffffff"  # 卡片面
    BG_INPUT: str = "#f3f5f9"  # 内凹输入区
    BG_HOVER: str = "#f6f8fb"  # 悬停
    BG_SELECT: str = "#e8f1fc"  # 选中浅底

    # 边框（极淡，仅作存在性暗示）
    BORDER: str = "#e4e9f0"
    BORDER_LIGHT: str = "#edf1f6"

    # 侧栏（深色浮动卡）
    INK: str = "#131a26"
    INK_SOFT: str = "#1c2637"
    INK_TEXT: str = "#e8edf5"
    INK_TEXT_MUTED: str = "#8fa3c0"
    INK_DIVIDER: str = "#1f2937"

    # 文字
    TEXT_PRIMARY: str = "#101828"
    TEXT_SECONDARY: str = "#475467"
    TEXT_MUTED: str = "#667085"
    TEXT_PLACEHOLDER: str = "#98a2b3"

    # 主强调色：云蓝（覆写 journal 默认砖红，与错误红拉开语义距离）
    ACCENT: str = "#1668dc"
    ACCENT_HOVER: str = "#1259b8"
    ACCENT_LIGHT: str = "#e8f1fc"
    ACCENT_BORDER: str = "#b9d4f5"

    # 语义色
    GREEN: str = "#16a34a"
    GREEN_BG: str = "#e8f6ee"
    GREEN_BORDER: str = "#b7e4c7"
    GREEN_TEXT: str = "#15803d"
    GREEN_HOVER: str = "#128a3e"

    RED: str = "#dc2626"
    RED_BG: str = "#fdecec"
    RED_BORDER: str = "#f5c2c2"
    RED_TEXT: str = "#b91c1c"
    RED_HOVER: str = "#c21e1e"

    YELLOW: str = "#d97706"
    YELLOW_BG: str = "#fef0c7"
    YELLOW_BORDER: str = "#f0c866"
    YELLOW_TEXT: str = "#b54708"

    PURPLE: str = "#8a63ab"
    PURPLE_BG: str = "#f5f0f9"
    PURPLE_BORDER: str = "#dccee6"
    PURPLE_TEXT: str = "#6d4b8c"
    PURPLE_HOVER: str = "#7c4fa3"

    # 选中态
    SELECTED_BG: str = "#1668dc"
    SELECTED_TEXT: str = "#ffffff"

    # 结果反馈
    CORRECT_BG: str = "#16a34a"
    CORRECT_TEXT: str = "#ffffff"
    CORRECT_HINT_BG: str = "#e8f6ee"
    CORRECT_HINT_TEXT: str = "#15803d"
    WRONG_BG: str = "#dc2626"
    WRONG_TEXT: str = "#ffffff"

    # 按钮
    BTN_PRIMARY: str = "#1668dc"
    BTN_PRIMARY_FG: str = "#ffffff"
    BTN_PRIMARY_HOVER: str = "#1259b8"
    BTN_PRIMARY_ACTIVE: str = "#0e4890"
    BTN_NORMAL: str = "#ffffff"
    BTN_NORMAL_FG: str = "#344054"
    BTN_NORMAL_HOVER: str = "#f6f8fb"
    BTN_NORMAL_ACTIVE: str = "#edf1f6"
    BTN_DISABLED: str = "#edf1f6"
    BTN_DISABLED_FG: str = "#98a2b3"

    # Tab（与主色一致）
    TAB_ACTIVE_FG: str = "#1668dc"
    TAB_ACTIVE_BORDER: str = "#1668dc"
    TAB_INACTIVE_FG: str = "#667085"

    # 就绪度环（分段渐变弧 + 轨道）
    RING_START: str = "#67c8f5"
    RING_END: str = "#1668dc"
    RING_TRACK: str = "#1f2937"

    # 考试倒计时 Pill（琥珀）
    TIMER_FG: str = "#b54708"
    TIMER_BG: str = "#fef0c7"
    TIMER_BORDER: str = "#f0c866"


# 夜航（深色）：深蓝黑页底 + 亮蓝主色，层次靠明度不靠边框
_DARK_TOKENS: dict[str, str] = {
    "BG_PAGE": "#0b0f16",
    "BG_CARD": "#131a26",
    "BG_INPUT": "#1b2433",
    "BG_HOVER": "#17202e",
    "BG_SELECT": "#16233b",
    "BORDER": "#1f2937",
    "BORDER_LIGHT": "#1b2433",
    "INK": "#0f1520",
    "INK_SOFT": "#1a2334",
    "INK_TEXT": "#e6eaf2",
    "INK_TEXT_MUTED": "#7e8ba0",
    "INK_DIVIDER": "#1e2635",
    "TEXT_PRIMARY": "#dde4ef",
    "TEXT_SECONDARY": "#8b94a7",
    "TEXT_MUTED": "#7e8aa0",
    "TEXT_PLACEHOLDER": "#5e6b84",
    "ACCENT": "#4c8dff",
    "ACCENT_HOVER": "#6da3ff",
    "ACCENT_LIGHT": "#16233b",
    "ACCENT_BORDER": "#2e4a73",
    "GREEN": "#34d399",
    "GREEN_BG": "#0f2b22",
    "GREEN_BORDER": "#1d4a3b",
    "GREEN_TEXT": "#6ee7b7",
    "GREEN_HOVER": "#2fb98a",
    "RED": "#f87171",
    "RED_BG": "#2b1416",
    "RED_BORDER": "#4a2326",
    "RED_TEXT": "#fca5a5",
    "RED_HOVER": "#e85d5d",
    "YELLOW": "#fbbf24",
    "YELLOW_BG": "#2b2113",
    "YELLOW_BORDER": "#4a3a1d",
    "YELLOW_TEXT": "#fcd34d",
    "PURPLE": "#a78bfa",
    "PURPLE_BG": "#221b33",
    "PURPLE_BORDER": "#3a2f52",
    "PURPLE_TEXT": "#c4b5fd",
    "PURPLE_HOVER": "#8f74e8",
    "SELECTED_BG": "#4c8dff",
    "SELECTED_TEXT": "#0b1220",
    "CORRECT_BG": "#34d399",
    "CORRECT_TEXT": "#052e22",
    "CORRECT_HINT_BG": "#0f2b22",
    "CORRECT_HINT_TEXT": "#6ee7b7",
    "WRONG_BG": "#f87171",
    "WRONG_TEXT": "#2b0d0d",
    "BTN_PRIMARY": "#4c8dff",
    "BTN_PRIMARY_FG": "#0b1220",
    "BTN_PRIMARY_HOVER": "#6da3ff",
    "BTN_PRIMARY_ACTIVE": "#2e6fe0",
    "BTN_NORMAL": "#1a2334",
    "BTN_NORMAL_FG": "#c6d0e0",
    "BTN_NORMAL_HOVER": "#223049",
    "BTN_NORMAL_ACTIVE": "#1a2334",
    "BTN_DISABLED": "#1a2334",
    "BTN_DISABLED_FG": "#5e6b84",
    "TAB_ACTIVE_FG": "#7fb0ff",
    "TAB_ACTIVE_BORDER": "#4c8dff",
    "TAB_INACTIVE_FG": "#7e8aa0",
    "RING_START": "#a5b4fc",
    "RING_END": "#38bdf8",
    "RING_TRACK": "#1b2433",
    "TIMER_FG": "#fbbf24",
    "TIMER_BG": "#2b2113",
    "TIMER_BORDER": "#4a3a1d",
}

# 模块级单例：所有 UI 组件共享同一 Theme 实例
theme = Theme()

# 当前主题模式（"light" / "dark"），set_theme_mode 维护
_current_mode: str = THEME_LIGHT

# 浅色快照（dataclass 默认值），供切回浅色使用
_LIGHT_TOKENS: dict[str, str] = {f.name: getattr(theme, f.name) for f in fields(theme)}


def _sync_module_constants() -> None:
    """把 theme 单例字段同步到模块级全局（兼容 `from ui.theme import BG_PAGE` 形式）。

    动态写入 globals，mypy 不可见——无静态引用方（全库经 theme.XXX 访问）。
    """
    _g = globals()
    for _f in fields(Theme):
        _g[_f.name] = getattr(theme, _f.name)


_sync_module_constants()


def current_theme_mode() -> str:
    """返回当前主题模式（"light" / "dark"）。"""
    return _current_mode


def set_theme_mode(mode: str) -> str:
    """切换主题：原地更新 theme 单例字段 + 同步模块级常量。

    调用方负责在切换后重建界面（控件创建时读 Token，重建即换肤）。
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
    _sync_module_constants()
    return normalized


def apply_theme_primary(window: Any) -> None:
    """按当前主题覆写 ttkbootstrap journal 主色（ttk 控件层）。

    tk.* 控件经本模块常量取色；ttk 控件（Combobox/Treeview/bootstyle
    按钮）取色于 ttkbootstrap 主题定义——在定义层覆写 primary 并重新
    应用主题，两套控件保持同色。切主题后必须重调本函数（K15）。
    [VERSION_LOCKED] ttkbootstrap 1.10.1：Colors 对象无 update 方法，
    须直接改属性后 theme_use 重应用触发样式重建。
    """
    style = window.style
    journal_def = style._theme_definitions["journal"]  # noqa: SLF001 上游无公开覆写 API
    journal_def.colors.primary = theme.ACCENT
    style.theme_use("journal")


# 旧名保留（main_window 等调用点迁移到 apply_theme_primary 前的过渡别名）
apply_ink_blue_primary = apply_theme_primary


def _hex_to_colorref(hex_color: str) -> int:
    """#rrggbb → Windows COLORREF（0x00BBGGRR，BGR 字节序）。"""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (b << 16) | (g << 8) | r


def apply_caption_color(window: Any) -> None:
    """窗口标题栏颜色跟随当前主题。

    优先 Win11 精确着色（DWMWA_CAPTION_COLOR 35 / TEXT_COLOR 36，标题栏
    取 theme.BG_PAGE、文字取 theme.TEXT_PRIMARY）；不支持时（Win10 1809+）
    降级 DWMWA_USE_IMMERSIVE_DARK_MODE(20)——深色主题配深色标题栏、浅色
    主题用系统默认浅色；再不支持（Win10 1809 前/非 Windows）保持系统
    默认并记 debug 日志。COLORREF 字节序为 0x00BBGGRR（BGR）。
    本机实测（Win10 22H2, build 19045）：35/36 返回 E_INVALIDARG，20 可用。
    """
    if platform.system() != "Windows":
        return
    try:
        import ctypes

        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        if not hwnd:
            logger.debug("标题栏着色跳过：未取得顶层窗口句柄")
            return
        dwm = ctypes.windll.dwmapi

        caption = ctypes.c_uint(_hex_to_colorref(theme.BG_PAGE))
        text = ctypes.c_uint(_hex_to_colorref(theme.TEXT_PRIMARY))
        rc_caption = dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(caption), 4)
        rc_text = dwm.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(text), 4)
        if rc_caption == 0 and rc_text == 0:
            return

        # Win10 降级：沉浸式深色标题栏（1=深 / 0=系统默认浅）
        immersive = ctypes.c_uint(1 if current_theme_mode() == "dark" else 0)
        rc_dark = dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(immersive), 4)
        if rc_dark != 0:
            logger.debug(
                "标题栏着色不受当前系统支持（rc=%d/%d/%d），保持系统默认",
                rc_caption,
                rc_text,
                rc_dark,
            )
    except (OSError, AttributeError) as e:
        logger.debug("标题栏着色不可用: %s", e)


def font_ui(size: int = 11, bold: bool = False) -> tuple[str, int, str] | tuple[str, int]:
    """正文/UI 字体（雅黑）。极简风默认 regular，必要时显式 bold。"""
    name = _get_fonts()["ui"]
    if bold:
        return (name, size, "bold")
    return (name, size)


def font_ui_semibold(size: int = 11) -> tuple[str, int, str]:
    """标签/按钮的次级强调字重（Tkinter 仅支持 bold，故复用）。"""
    return (_get_fonts()["ui"], size, "bold")


def font_mono(size: int = 12) -> tuple[str, int]:
    """计时器/数字数据用等宽，避免布局漂移。"""
    return (_get_fonts()["mono"], size)


def font_display(size: int = 16, bold: bool = True) -> tuple[str, int, str] | tuple[str, int]:
    """标题字体——与正文同族（全面雅黑），靠字号/字重分层。"""
    name = _get_fonts()["display"]
    if bold:
        return (name, size, "bold")
    return (name, size)


# ---------------------------------------------------------------------------
# UI 组件工厂函数 —— 集中按钮 / 卡片 / 开关 / 芯片样式，避免各处重复配置
# ---------------------------------------------------------------------------


def create_primary_button(
    parent: tk.Misc,
    text: str = "",
    command: Callable[[], None] | None = None,
    bg_color: str | None = None,
    active_bg: str | None = None,
    width: int = 0,
    padx: int = 16,
    pady: int = 6,
) -> RoundedButton:
    """创建主按钮（圆角，白字 + 云蓝底，默认教育蓝）。

    bg_color 可替换为 RED / GREEN / PURPLE / YELLOW 等语义色，用于交卷、
    标记、显示答案等特殊场景；文字色取 BTN_PRIMARY_FG（深色主题下亮色
    按钮配深字，对比度达标）。
    """
    bg = bg_color or theme.BTN_PRIMARY
    hover = active_bg or theme.BTN_PRIMARY_HOVER
    height = max(28, 2 * pady + 18)
    return RoundedButton(
        parent,
        text,
        command,
        font=font_ui_semibold(12),
        bg=bg,
        fg=theme.BTN_PRIMARY_FG,
        hover_bg=hover,
        active_bg=hover,
        disabled_bg=theme.BTN_DISABLED,
        disabled_fg=theme.BTN_DISABLED_FG,
        radius=RADIUS_BTN,
        padx=padx,
        height=height,
        width=width,
    )


def create_normal_button(
    parent: tk.Misc,
    text: str = "",
    command: Callable[[], None] | None = None,
    font_size: int = 11,
    padx: int = 12,
    pady: int = 5,
    width: int = 0,
) -> RoundedButton:
    """创建普通按钮（圆角，深色字 + 白底，轻量视觉）。"""
    height = max(26, 2 * pady + 16)
    return RoundedButton(
        parent,
        text,
        command,
        font=font_ui(font_size),
        bg=theme.BTN_NORMAL,
        fg=theme.BTN_NORMAL_FG,
        hover_bg=theme.BTN_NORMAL_HOVER,
        active_bg=theme.BTN_NORMAL_ACTIVE,
        disabled_bg=theme.BTN_DISABLED,
        disabled_fg=theme.BTN_DISABLED_FG,
        radius=RADIUS_BTN,
        padx=padx,
        height=height,
        width=width,
    )


def create_card(
    parent: tk.Misc,
    inner_padx: int = 20,
    inner_pady: int = 16,
    *,
    radius: int = RADIUS_CARD,
    bg: str | None = None,
    surface: str | None = None,
    border: str | None = None,
) -> tuple[RoundedCard, tk.Frame]:
    """创建圆角卡片容器，返回 (card, inner)。

    card 是 Canvas（未 pack），inner 是内容 Frame（inset = radius，
    视觉内边距 ≈ inner_padx/inner_pady，见 rounded.py K4）。
    调用方负责 pack card，然后往 inner 里填充内容即可。
    """
    card = RoundedCard(
        parent,
        radius=radius,
        bg=bg if bg is not None else theme.BG_CARD,
        surface=surface if surface is not None else theme.BG_PAGE,
        border=border if border is not None else theme.BORDER,
        padx=max(4, inner_padx - radius),
        pady=max(4, inner_pady - radius),
    )
    return card, card.inner


def create_switch(
    parent: tk.Misc,
    variable: tk.BooleanVar | None = None,
    command: Callable[[], None] | None = None,
) -> Switch:
    """创建圆角开关（替代 tk.Checkbutton，随机出题/自动显示答案用）。"""
    return Switch(
        parent,
        variable,
        command,
        on_bg=theme.ACCENT,
        off_bg=theme.BORDER,
        knob_color="#ffffff",
    )


def create_chip(
    parent: tk.Misc,
    text: str = "",
    *,
    bg: str | None = None,
    fg: str | None = None,
    font: Any = None,
) -> Chip:
    """创建小胶囊标签（题型 / 统计 / 状态提示）。"""
    return Chip(
        parent,
        text,
        font=font or font_ui(11),
        bg=bg if bg is not None else theme.ACCENT_LIGHT,
        fg=fg if fg is not None else theme.ACCENT,
    )


def center_window(window: tk.Tk | tk.Toplevel) -> None:
    """把窗口居中到屏幕中央（先取真实尺寸再算坐标）。"""
    window.update_idletasks()
    width = window.winfo_width()
    height = window.winfo_height()
    x = (window.winfo_screenwidth() // 2) - (width // 2)
    y = (window.winfo_screenheight() // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


def autofit_text_height(
    text: tk.Text, min_lines: int = 3, max_lines: int = 16, min_width: int = 120
) -> None:
    """按内容实际显示行数调整只读 Text 的高度（P3：长题干不再被固定行数裁切）。

    用 displaylines 计数（含 wrap 换行的真实渲染行数）。控件尚未完成布局
    （winfo_width < min_width）时跳过——用病态窄宽度计算会得到虚假的巨大
    行数并把高度顶到 max_lines 卡死（须等后续 Configure 事件纠正，窗口
    不再变化时永远等不到）。绑定到 Text 自身的 <Configure> 后，宽度真实
    到位/变化时必然重算并收敛。TclError 仅在控件已销毁时发生。
    """
    try:
        if text.winfo_width() < min_width:
            return
        result = text.count("1.0", "end-1c", "displaylines")
    except tk.TclError:
        return
    lines = result[0] if isinstance(result, tuple) else result
    if not isinstance(lines, int):
        return
    text.configure(height=max(min_lines, min(lines, max_lines)))
