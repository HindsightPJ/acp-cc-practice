import platform
import tkinter as tk
from tkinter import font as tkfont


def _list_system_fonts():
    """查询系统真实可用字体集合。

    复用已有 Tk root（若存在），避免创建多余 root 导致 Tcl 状态冲突。
    无头环境或无 root 时返回空集合，由 fallback 兜底。
    """
    try:
        root = tk._default_root
        if root is not None:
            return set(tkfont.families(root))
        return set()
    except tk.TclError:
        # 无头环境或 Tk root 状态异常时，返回空集合由 fallback 兜底
        return set()


_AVAILABLE_FONTS = None
_FONTS_CACHE = None


def _get_fonts():
    """懒加载字体配置：首次调用时检测系统字体，避免模块导入时创建 Tk root。"""
    global _FONTS_CACHE
    if _FONTS_CACHE is None:
        _FONTS_CACHE = _detect_fonts_impl()
    return _FONTS_CACHE


def _detect_fonts_impl():
    """Glassmorphism 极简风字体栈：Inter 优先，fallback 到系统现代字体。

    Inter 是 Google 免费字体，粗细对比鲜明，是现代 UI 设计的首选。
    若系统未安装 Inter，按优先级 fallback 到 Segoe UI Variable (Win11) /
    Microsoft YaHei UI (Win10) / Segoe UI，保证中文渲染。
    通过 _list_system_fonts 真实查询，避免指定不存在的字体被 Tkinter
    静默替换为默认字体（会破坏粗细对比）。
    """
    global _AVAILABLE_FONTS
    _AVAILABLE_FONTS = _list_system_fonts()
    system = platform.system()
    available = _AVAILABLE_FONTS

    def _pick(preferred, fallback):
        # 从优先级列表里挑第一个系统真实安装的字体
        for name in preferred:
            if name in available:
                return name
        return fallback

    if system == "Windows":
        ui = _pick(
            [
                "Inter",
                "Inter Variable",
                "Segoe UI Variable Text",
                "Segoe UI Variable",
                "Microsoft YaHei UI",
                "Segoe UI",
            ],
            "Segoe UI",
        )
        emoji = _pick(["Segoe UI Emoji", "Segoe UI Symbol"], "Segoe UI")
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
        # display 用于标题，优先 Inter / Segoe UI Variable（粗细更分明）
        display = _pick(
            [
                "Inter",
                "Inter Variable",
                "Segoe UI Variable Display",
                "Segoe UI Variable",
                "Microsoft YaHei UI",
                "Segoe UI",
            ],
            "Segoe UI",
        )
    elif system == "Darwin":
        ui = _pick(
            [
                "Inter",
                "SF Pro Text",
                ".SF NS Text",
                "PingFang SC",
                "Helvetica Neue",
            ],
            "Helvetica Neue",
        )
        emoji = _pick(["Apple Color Emoji"], "Helvetica Neue")
        mono = _pick(
            [
                "JetBrains Mono",
                "Fira Code",
                "SF Mono",
                "Menlo",
            ],
            "Menlo",
        )
        display = _pick(
            [
                "Inter",
                "SF Pro Display",
                ".SF NS Display",
                "PingFang SC",
                "Helvetica Neue",
            ],
            "Helvetica Neue",
        )
    else:
        ui = _pick(
            [
                "Inter",
                "Noto Sans CJK SC",
                "WenQuanYi Micro Hei",
                "DejaVu Sans",
            ],
            "DejaVu Sans",
        )
        emoji = _pick(["Noto Color Emoji"], "DejaVu Sans")
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
                "Inter",
                "Noto Sans CJK SC",
                "WenQuanYi Micro Hei",
                "DejaVu Sans",
            ],
            "DejaVu Sans",
        )

    return {
        "ui": ui,
        "emoji": emoji,
        "mono": mono,
        "display": display,
    }


# --- 设计 Token：Quiet Academy ----------------------------------------
# 极简教育风：以纯白为主、教育蓝为单一强调色，配 macOS 风深灰侧栏。
# 刻意减少颜色种类——除主色外仅保留必要的语义色（success/warn/error），
# 其他全部灰阶。文字层级靠字重和明度差，不靠色相。

# 页面与卡片
BG_PAGE = "#fafafa"  # APP BACKGROUND — 微灰，避免纯白刺眼
BG_CARD = "#ffffff"  # SURFACE
BG_INPUT = "#f5f5f7"  # INSET — macOS 输入框底色
BG_HOVER = "#f0f0f2"  # HOVER 灰
BG_SELECT = "#eef4ff"  # SELECT 浅蓝

# 边框（极简风：单一极淡灰）
BORDER = "#e5e7eb"  # RULE
BORDER_LIGHT = "#f0f0f2"

# 侧栏（macOS 深灰，非蓝紫调）
INK = "#1c1c1e"  # SIDEBAR BG (iOS dark)
INK_SOFT = "#2c2c2e"  # SIDEBAR HOVER
INK_TEXT = "#f5f5f7"  # SIDEBAR PRIMARY TEXT
INK_TEXT_MUTED = "#8e8e93"  # SIDEBAR SECONDARY TEXT
INK_DIVIDER = "#38383a"

# 文字（纯黑系，无色相）
TEXT_PRIMARY = "#111814"
TEXT_SECONDARY = "#6b7280"
TEXT_MUTED = "#9ca3af"
TEXT_PLACEHOLDER = "#cbd5e1"

# 主强调色：教育蓝 blue-600（替代原琥珀色，更"知识/专注/学术"）
ACCENT = "#2563eb"
ACCENT_HOVER = "#1d4ed8"
ACCENT_LIGHT = "#eff6ff"
ACCENT_BORDER = "#bfdbfe"

# 语义色（保留，用于正确/警告/错误反馈）
GREEN = "#059669"
GREEN_BG = "#ecfdf5"
GREEN_BORDER = "#a7f3d0"
GREEN_TEXT = "#065f46"

RED = "#dc2626"
RED_BG = "#fef2f2"
RED_BORDER = "#fecaca"
RED_TEXT = "#991b1b"

YELLOW = "#d97706"
YELLOW_BG = "#fffbeb"
YELLOW_BORDER = "#fde68a"
YELLOW_TEXT = "#92400e"

PURPLE = "#7c3aed"
PURPLE_BG = "#faf5ff"
PURPLE_BORDER = "#e9d5ff"
PURPLE_TEXT = "#6b21a8"

# 选中态
SELECTED_BG = "#2563eb"
SELECTED_TEXT = "#ffffff"

# 结果反馈（与语义色一致）
CORRECT_BG = "#059669"
CORRECT_TEXT = "#ffffff"
CORRECT_HINT_BG = "#ecfdf5"
CORRECT_HINT_TEXT = "#065f46"
WRONG_BG = "#dc2626"
WRONG_TEXT = "#ffffff"

# 按钮
BTN_PRIMARY = "#2563eb"
BTN_PRIMARY_HOVER = "#1d4ed8"
BTN_PRIMARY_ACTIVE = "#1e40af"
BTN_NORMAL = "#ffffff"
BTN_NORMAL_FG = "#374151"
BTN_NORMAL_HOVER = "#f3f4f6"
BTN_NORMAL_ACTIVE = "#e5e7eb"
BTN_DISABLED = "#f3f4f6"
BTN_DISABLED_FG = "#9ca3af"

# Tab（与主色一致）
TAB_ACTIVE_FG = "#2563eb"
TAB_ACTIVE_BORDER = "#2563eb"
TAB_INACTIVE_FG = "#8e8e93"


def font_ui(size=11, bold=False):
    """正文/UI 字体。极简风默认 regular，必要时显式 bold。"""
    name = _get_fonts()["ui"]
    if bold:
        return (name, size, "bold")
    return (name, size)


def font_ui_semibold(size=11):
    """标签/按钮的次级强调字重（Tkinter 仅支持 bold，故复用）。"""
    return (_get_fonts()["ui"], size, "bold")


def font_emoji(size=14):
    return (_get_fonts()["emoji"], size)


def font_mono(size=12):
    """计时器/数字数据用等宽，避免布局漂移。"""
    return (_get_fonts()["mono"], size)


def font_display(size=16, bold=True):
    """标题字体——使用 display 字族，字号偏大。"""
    if bold:
        return (_get_fonts()["display"], size, "bold")
    return (_get_fonts()["display"], size)


# ---------------------------------------------------------------------------
# UI 组件工厂函数 —— 集中按钮 / 卡片样式，避免各处重复配置
# ---------------------------------------------------------------------------


def create_primary_button(
    parent,
    text="",
    command=None,
    bg_color=None,
    active_bg=None,
    width=0,
    padx=16,
    pady=6,
):
    """创建主按钮（白字 + 强调色底，默认教育蓝）。

    bg_color 可替换为 RED / GREEN / PURPLE 等语义色，用于交卷、标记等特殊场景。
    """
    bg = bg_color or BTN_PRIMARY
    active = active_bg or BTN_PRIMARY_HOVER
    btn = tk.Button(
        parent,
        text=text,
        command=command,
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

    def on_enter(e):
        btn.configure(bg=active)

    def on_leave(e):
        btn.configure(bg=bg)

    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)
    return btn


def create_normal_button(
    parent,
    text="",
    command=None,
    font_size=10,
    padx=12,
    pady=5,
    width=0,
):
    """创建普通按钮（深色字 + 白底，轻量视觉）。"""
    btn = tk.Button(
        parent,
        text=text,
        command=command,
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

    def on_enter(e):
        btn.configure(bg=BTN_NORMAL_HOVER)

    def on_leave(e):
        btn.configure(bg=BTN_NORMAL)

    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)
    return btn


def create_card(parent, inner_padx=20, inner_pady=16):
    """创建带边框的卡片容器，返回 (card, inner)。

    card 是外层边框 Frame（未 pack），inner 是内层内容 Frame（已设置 padding）。
    调用方负责 pack card，然后往 inner 里填充内容即可。
    """
    card = tk.Frame(
        parent, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1
    )
    inner = tk.Frame(card, bg=BG_CARD)
    inner.pack(fill=tk.BOTH, expand=True, padx=inner_padx, pady=inner_pady)
    return card, inner


class Theme:
    """主题访问器：以属性方式读取本模块定义的全局颜色常量。

    用法：
        theme = Theme()
        frame = tk.Frame(parent, bg=theme.BG_PAGE)
    """

    def __getattr__(self, name: str) -> str:
        if name.startswith("_"):
            raise AttributeError(name)
        return globals()[name]

    def __dir__(self):
        return sorted(
            name
            for name in globals()
            if name.isupper() and isinstance(globals()[name], str) and name[0] != "_"
        )
