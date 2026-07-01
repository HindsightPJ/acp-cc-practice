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
# 暗色模式支持（TD-33）
# ---------------------------------------------------------------------------
# 保持上面的常量作为浅色默认值；动态主题通过 Theme 类获取。
_DARK_MODE = False

_DARK_TOKENS = {
    "BG_PAGE": "#121212",
    "BG_CARD": "#1e1e1e",
    "BG_INPUT": "#2c2c2e",
    "BG_HOVER": "#2c2c2e",
    "BG_SELECT": "#1e3a8a",
    "BORDER": "#38383a",
    "BORDER_LIGHT": "#2c2c2e",
    "INK": "#000000",
    "INK_SOFT": "#1c1c1e",
    "INK_TEXT": "#f5f5f7",
    "INK_TEXT_MUTED": "#8e8e93",
    "INK_DIVIDER": "#38383a",
    "TEXT_PRIMARY": "#f5f5f7",
    "TEXT_SECONDARY": "#a1a1aa",
    "TEXT_MUTED": "#71717a",
    "TEXT_PLACEHOLDER": "#52525b",
    "ACCENT": "#3b82f6",
    "ACCENT_HOVER": "#2563eb",
    "ACCENT_LIGHT": "#1e3a8a",
    "ACCENT_BORDER": "#3b82f6",
    "GREEN": "#34d399",
    "GREEN_BG": "#064e3b",
    "GREEN_BORDER": "#059669",
    "GREEN_TEXT": "#6ee7b7",
    "RED": "#f87171",
    "RED_BG": "#7f1d1d",
    "RED_BORDER": "#dc2626",
    "RED_TEXT": "#fca5a5",
    "YELLOW": "#fbbf24",
    "YELLOW_BG": "#78350f",
    "YELLOW_BORDER": "#d97706",
    "YELLOW_TEXT": "#fde68a",
    "PURPLE": "#a78bfa",
    "PURPLE_BG": "#4c1d95",
    "PURPLE_BORDER": "#7c3aed",
    "PURPLE_TEXT": "#ddd6fe",
    "SELECTED_BG": "#3b82f6",
    "SELECTED_TEXT": "#ffffff",
    "CORRECT_BG": "#059669",
    "CORRECT_TEXT": "#ffffff",
    "CORRECT_HINT_BG": "#064e3b",
    "CORRECT_HINT_TEXT": "#6ee7b7",
    "WRONG_BG": "#dc2626",
    "WRONG_TEXT": "#ffffff",
    "BTN_PRIMARY": "#3b82f6",
    "BTN_PRIMARY_HOVER": "#2563eb",
    "BTN_PRIMARY_ACTIVE": "#1d4ed8",
    "BTN_NORMAL": "#1e1e1e",
    "BTN_NORMAL_FG": "#f5f5f7",
    "BTN_NORMAL_HOVER": "#2c2c2e",
    "BTN_NORMAL_ACTIVE": "#3f3f46",
    "BTN_DISABLED": "#27272a",
    "BTN_DISABLED_FG": "#71717a",
    "TAB_ACTIVE_FG": "#3b82f6",
    "TAB_ACTIVE_BORDER": "#3b82f6",
    "TAB_INACTIVE_FG": "#a1a1aa",
}

# 自动收集当前浅色值，避免维护两套重复映射。
_LIGHT_TOKENS = {name: globals()[name] for name in _DARK_TOKENS if name in globals()}


def set_dark_mode(enabled: bool) -> None:
    """切换全局暗色模式开关。

    该开关影响之后通过 Theme 实例读取的所有颜色值。已创建的 UI 组件
    如需响应切换，应重新读取颜色并更新自身样式。
    """
    global _DARK_MODE
    _DARK_MODE = bool(enabled)


def is_dark_mode() -> bool:
    """当前是否处于暗色模式。"""
    return _DARK_MODE


def color(name: str) -> str:
    """根据当前模式返回指定 token 的颜色值。

    若 token 不存在，回退到常量值；若常量也不存在则抛出 KeyError。
    """
    if name in _DARK_TOKENS and _DARK_MODE:
        return _DARK_TOKENS[name]
    fallback: str = _LIGHT_TOKENS.get(name, globals()[name])
    return fallback


class Theme:
    """动态主题访问器。

    用法：
        theme = Theme()
        frame = tk.Frame(parent, bg=theme.BG_PAGE)

    颜色值会随 set_dark_mode() 的切换而变化，因此适合在运行时重新应用主题。
    """

    def __getattr__(self, name: str) -> str:
        if name.startswith("_"):
            raise AttributeError(name)
        return color(name)

    def set_dark_mode(self, enabled: bool) -> None:
        set_dark_mode(enabled)

    def is_dark_mode(self) -> bool:
        return is_dark_mode()

    def __dir__(self):
        return sorted(_LIGHT_TOKENS.keys())
