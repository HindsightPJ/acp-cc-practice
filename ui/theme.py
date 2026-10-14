from dataclasses import dataclass
import platform
import tkinter as tk
from tkinter import font as tkfont
from typing import Any, Callable, cast


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
    """Journal 纸感字体栈：Georgia（西文衬线）+ 宋体（中文）。

    题干/标题用 Georgia——Windows GDI 字体链接会让 Georgia 缺失的 CJK
    字形自动回退到宋体系，形成「西文衬线 + 中文宋体」的经典纸书效果；
    正文/选项直接指定宋体，保证中文渲染不走雅黑回退。
    通过 _list_system_fonts 真实查询，避免指定不存在的字体被 Tkinter
    静默替换为默认字体。
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
        # 宋体优先（中文注册名），兼容英文注册名 SimSun
        ui = _pick(["宋体", "SimSun"], "Microsoft YaHei UI")
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
        # display 用于标题/题干：Georgia 西文衬线 + CJK 字形回退宋体
        display = _pick(["Georgia", "Cambria"], "宋体")
    elif system == "Darwin":
        ui = _pick(["宋体", "SimSun", "Songti SC", "STSong"], "Songti SC")
        mono = _pick(
            [
                "JetBrains Mono",
                "Fira Code",
                "SF Mono",
                "Menlo",
            ],
            "Menlo",
        )
        display = _pick(["Georgia"], "Times New Roman")
    else:
        ui = _pick(
            [
                "Noto Serif CJK SC",
                "AR PL UMing CN",
                "SimSun",
            ],
            "DejaVu Serif",
        )
        mono = _pick(
            [
                "JetBrains Mono",
                "Fira Code",
                "DejaVu Sans Mono",
            ],
            "DejaVu Sans Mono",
        )
        display = _pick(
            [
                "Georgia",
                "Liberation Serif",
                "DejaVu Serif",
            ],
            "DejaVu Serif",
        )

    return {
        "ui": ui,
        "mono": mono,
        "display": display,
    }


# --- 设计 Token：Journal 纸感 + 墨蓝主色 ---------------------------------
# 对齐 ttkbootstrap journal 主题（2026-09-01 本机实测：bg #ffffff /
# border #ced4da / success #22b24c；primary 默认砖红 #eb6864 已覆写为
# 墨蓝）。暖白纸面 + 白卡片 + 墨蓝单一强调色；文字层级靠字重和明度差，
# 不靠色相。墨蓝与错误反馈红拉开语义距离，避免刷题场景混淆品牌色与
# 答错提示。

# 页面与卡片
BG_PAGE = "#f8f6f1"  # APP BACKGROUND — 暖白纸面，避免纯白刺眼
BG_CARD = "#ffffff"  # SURFACE
BG_INPUT = "#f4f1ea"  # INSET — 纸面内凹输入区
BG_HOVER = "#eeeae1"  # HOVER 暖灰
BG_SELECT = "#e7eef5"  # SELECT 浅墨蓝

# 边框（暖灰调，与 journal 边框同族但更暖）
BORDER = "#ddd8cc"  # RULE
BORDER_LIGHT = "#eceae2"

# 侧栏（深墨色，与 journal dark #222222 一致）
INK = "#1c1c1e"  # SIDEBAR BG
INK_SOFT = "#2c2c2e"  # SIDEBAR HOVER
INK_TEXT = "#f5f5f7"  # SIDEBAR PRIMARY TEXT
INK_TEXT_MUTED = "#8e8e93"  # SIDEBAR SECONDARY TEXT
INK_DIVIDER = "#38383a"

# 文字（深墨系，无色相）
TEXT_PRIMARY = "#222222"
TEXT_SECONDARY = "#666666"
TEXT_MUTED = "#8f8a82"
TEXT_PLACEHOLDER = "#c9c4b8"

# 主强调色：墨蓝（覆写 journal 默认砖红，避免与错误红语义冲突）
ACCENT = "#2f5d8a"
ACCENT_HOVER = "#27507a"
ACCENT_LIGHT = "#e9f0f7"
ACCENT_BORDER = "#bfd0e0"

# 语义色（success 对齐 journal #22b24c，红/黄/紫做纸感柔化）
GREEN = "#22b24c"
GREEN_BG = "#e8f6ec"
GREEN_BORDER = "#b5e0c1"
GREEN_TEXT = "#176e37"

RED = "#d64541"
RED_BG = "#fcefee"
RED_BORDER = "#f1c9c6"
RED_TEXT = "#a13431"

YELLOW = "#d97706"
YELLOW_BG = "#fffbeb"
YELLOW_BORDER = "#fde68a"
YELLOW_TEXT = "#92400e"

PURPLE = "#8a63ab"
PURPLE_BG = "#f5f0f9"
PURPLE_BORDER = "#dcccec"
PURPLE_TEXT = "#5e4380"

# 选中态
SELECTED_BG = "#2f5d8a"
SELECTED_TEXT = "#ffffff"

# 结果反馈（与语义色一致）
CORRECT_BG = "#22b24c"
CORRECT_TEXT = "#ffffff"
CORRECT_HINT_BG = "#e8f6ec"
CORRECT_HINT_TEXT = "#176e37"
WRONG_BG = "#d64541"
WRONG_TEXT = "#ffffff"

# 按钮
BTN_PRIMARY = "#2f5d8a"
BTN_PRIMARY_HOVER = "#27507a"
BTN_PRIMARY_ACTIVE = "#1f4166"
BTN_NORMAL = "#ffffff"
BTN_NORMAL_FG = "#444444"
BTN_NORMAL_HOVER = "#f4f1ea"
BTN_NORMAL_ACTIVE = "#e8e4da"
BTN_DISABLED = "#f1eee7"
BTN_DISABLED_FG = "#b0aba1"

# Tab（与主色一致）
TAB_ACTIVE_FG = "#2f5d8a"
TAB_ACTIVE_BORDER = "#2f5d8a"
TAB_INACTIVE_FG = "#8f8a82"


def apply_ink_blue_primary(window: Any) -> None:
    """将 ttkbootstrap journal 主色覆写为墨蓝（ttk 控件层）。

    tk.* 控件经本模块常量取色；ttk 控件（Combobox/Treeview/bootstyle
    按钮）取色于 ttkbootstrap 主题定义——在定义层覆写 primary 并重新
    应用主题，两套控件保持同色。
    [VERSION_LOCKED] ttkbootstrap 1.10.1：Colors 对象无 update 方法，
    须直接改属性后 theme_use 重应用触发样式重建。
    """
    style = window.style
    journal_def = style._theme_definitions["journal"]  # noqa: SLF001 上游无公开覆写 API
    journal_def.colors.primary = ACCENT
    style.theme_use("journal")


def font_ui(size: int = 11, bold: bool = False) -> tuple[str, int, str] | tuple[str, int]:
    """正文/UI 字体。极简风默认 regular，必要时显式 bold。"""
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
    """标题字体——使用 display 字族，字号偏大。"""
    if bold:
        return (_get_fonts()["display"], size, "bold")
    return (_get_fonts()["display"], size)


# ---------------------------------------------------------------------------
# UI 组件工厂函数 —— 集中按钮 / 卡片样式，避免各处重复配置
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
) -> tk.Button:
    """创建主按钮（白字 + 强调色底，默认教育蓝）。

    bg_color 可替换为 RED / GREEN / PURPLE 等语义色，用于交卷、标记等特殊场景。
    """
    bg = bg_color or BTN_PRIMARY
    active = active_bg or BTN_PRIMARY_HOVER
    btn = tk.Button(
        parent,
        text=text,
        command=cast(str | Callable[[], Any], command),
        font=font_ui_semibold(11),
        fg="#ffffff",
        bg=bg,
        activebackground=active,
        activeforeground="#ffffff",
        relief=tk.FLAT,
        width=width,
        padx=padx,
        pady=pady,
        cursor="hand2",
    )

    def on_enter(e: tk.Event) -> None:
        btn.configure(bg=active)

    def on_leave(e: tk.Event) -> None:
        btn.configure(bg=bg)

    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)
    return btn


def create_normal_button(
    parent: tk.Misc,
    text: str = "",
    command: Callable[[], None] | None = None,
    font_size: int = 10,
    padx: int = 12,
    pady: int = 5,
    width: int = 0,
) -> tk.Button:
    """创建普通按钮（深色字 + 白底，轻量视觉）。"""
    btn = tk.Button(
        parent,
        text=text,
        command=cast(str | Callable[[], Any], command),
        font=font_ui(font_size),
        fg=BTN_NORMAL_FG,
        bg=BTN_NORMAL,
        activebackground=BTN_NORMAL_HOVER,
        activeforeground=TEXT_PRIMARY,
        relief=tk.FLAT,
        width=width,
        padx=padx,
        pady=pady,
        cursor="hand2",
    )

    def on_enter(e: tk.Event) -> None:
        btn.configure(bg=BTN_NORMAL_HOVER)

    def on_leave(e: tk.Event) -> None:
        btn.configure(bg=BTN_NORMAL)

    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)
    return btn


def create_card(
    parent: tk.Misc, inner_padx: int = 20, inner_pady: int = 16
) -> tuple[tk.Frame, tk.Frame]:
    """创建带边框的卡片容器，返回 (card, inner)。

    card 是外层边框 Frame（未 pack），inner 是内层内容 Frame（已设置 padding）。
    调用方负责 pack card，然后往 inner 里填充内容即可。
    """
    card = tk.Frame(parent, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1)
    inner = tk.Frame(card, bg=BG_CARD)
    inner.pack(fill=tk.BOTH, expand=True, padx=inner_padx, pady=inner_pady)
    return card, inner


def center_window(window: tk.Tk | tk.Toplevel) -> None:
    """把窗口居中到屏幕中央（先取真实尺寸再算坐标）。"""
    window.update_idletasks()
    width = window.winfo_width()
    height = window.winfo_height()
    x = (window.winfo_screenwidth() // 2) - (width // 2)
    y = (window.winfo_screenheight() // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


@dataclass(frozen=True)
class Theme:
    """主题访问器：以属性方式读取本模块定义的全局颜色常量。

    用法：
        theme = Theme()
        frame = tk.Frame(parent, bg=theme.BG_PAGE)
    """

    BG_PAGE: str = BG_PAGE
    BG_CARD: str = BG_CARD
    BG_INPUT: str = BG_INPUT
    BG_HOVER: str = BG_HOVER
    BG_SELECT: str = BG_SELECT
    BORDER: str = BORDER
    BORDER_LIGHT: str = BORDER_LIGHT
    INK: str = INK
    INK_SOFT: str = INK_SOFT
    INK_TEXT: str = INK_TEXT
    INK_TEXT_MUTED: str = INK_TEXT_MUTED
    INK_DIVIDER: str = INK_DIVIDER
    TEXT_PRIMARY: str = TEXT_PRIMARY
    TEXT_SECONDARY: str = TEXT_SECONDARY
    TEXT_MUTED: str = TEXT_MUTED
    TEXT_PLACEHOLDER: str = TEXT_PLACEHOLDER
    ACCENT: str = ACCENT
    ACCENT_HOVER: str = ACCENT_HOVER
    ACCENT_LIGHT: str = ACCENT_LIGHT
    ACCENT_BORDER: str = ACCENT_BORDER
    GREEN: str = GREEN
    GREEN_BG: str = GREEN_BG
    GREEN_BORDER: str = GREEN_BORDER
    GREEN_TEXT: str = GREEN_TEXT
    RED: str = RED
    RED_BG: str = RED_BG
    RED_BORDER: str = RED_BORDER
    RED_TEXT: str = RED_TEXT
    YELLOW: str = YELLOW
    YELLOW_BG: str = YELLOW_BG
    YELLOW_BORDER: str = YELLOW_BORDER
    YELLOW_TEXT: str = YELLOW_TEXT
    PURPLE: str = PURPLE
    PURPLE_BG: str = PURPLE_BG
    PURPLE_BORDER: str = PURPLE_BORDER
    PURPLE_TEXT: str = PURPLE_TEXT
    SELECTED_BG: str = SELECTED_BG
    SELECTED_TEXT: str = SELECTED_TEXT
    CORRECT_BG: str = CORRECT_BG
    CORRECT_TEXT: str = CORRECT_TEXT
    CORRECT_HINT_BG: str = CORRECT_HINT_BG
    CORRECT_HINT_TEXT: str = CORRECT_HINT_TEXT
    WRONG_BG: str = WRONG_BG
    WRONG_TEXT: str = WRONG_TEXT
    BTN_PRIMARY: str = BTN_PRIMARY
    BTN_PRIMARY_HOVER: str = BTN_PRIMARY_HOVER
    BTN_PRIMARY_ACTIVE: str = BTN_PRIMARY_ACTIVE
    BTN_NORMAL: str = BTN_NORMAL
    BTN_NORMAL_FG: str = BTN_NORMAL_FG
    BTN_NORMAL_HOVER: str = BTN_NORMAL_HOVER
    BTN_NORMAL_ACTIVE: str = BTN_NORMAL_ACTIVE
    BTN_DISABLED: str = BTN_DISABLED
    BTN_DISABLED_FG: str = BTN_DISABLED_FG
    TAB_ACTIVE_FG: str = TAB_ACTIVE_FG
    TAB_ACTIVE_BORDER: str = TAB_ACTIVE_BORDER
    TAB_INACTIVE_FG: str = TAB_INACTIVE_FG


# 模块级单例：所有 UI 组件共享同一 Theme 实例（无状态访问器，等价于多次实例化）
theme = Theme()
