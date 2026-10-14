"""圆角 UI 基元：卡片 / 按钮 / 开关 / 芯片。

Tkinter 原生控件均为直角且无透明色，本模块用 Canvas 绘制圆角矩形，
文字仍走 Label / create_text，保证文本渲染、测试与键盘可达性不变。

设计约束（Tkinter 能力边界的对冲，见 TASK_PLAN K4）：
- RoundedCard 的内容窗口 inset = radius，避免嵌入 Frame 的矩形角
  盖住画布圆角（Tk 无裁剪，嵌入窗口探出圆角区会画出方角）；
- RoundedCard 自动高度取 shell 的 winfo_reqheight（内容自然高度），
  而非 <Configure> 事件高度（后者可能是窗口项强制的尺寸）；
- 本模块不 import theme（theme 的工厂函数反向依赖本模块），所有
  颜色由调用方显式传入，杜绝循环依赖与双取色源。
"""

import logging
import tkinter as tk
from tkinter import font as tkfont
from typing import Any, Callable, Literal

from .constants import RADIUS_BTN, RADIUS_CARD, RADIUS_CHIP

logger = logging.getLogger(__name__)


def _as_font_obj(spec: Any, master: tk.Misc) -> Any:
    """把 (family, size[, weight]) 元组转为 tkfont.Font（提供 .measure）。

    绑定到控件自身的 root（master=self）：Font 随控件根生灭，避免测试
    环境跨 root 复用缓存字体导致 TclError；无缓存即无失效。
    """
    if spec is None or hasattr(spec, "measure"):
        return spec
    if isinstance(spec, tuple) and len(spec) >= 2:
        family = str(spec[0])
        size = int(spec[1])
        weight: Literal["normal", "bold"] = "normal"
        for extra in spec[2:]:
            if str(extra).lower() == "bold":
                weight = "bold"
            elif str(extra).lower() == "normal":
                weight = "normal"
        # 位置传参：typeshed 首参名 master，Python 3.14 首参名 root，位置传参两者皆兼容
        return tkfont.Font(master, family=family, size=size, weight=weight)
    return spec


# Switch 尺寸（Canvas px）
SWITCH_WIDTH = 34
SWITCH_HEIGHT = 20
# Switch 滑块补间动画步数 / 间隔（毫秒）
SWITCH_ANIM_STEPS = 2
SWITCH_ANIM_INTERVAL_MS = 16


def draw_round_rect(
    canvas: tk.Canvas,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    radius: float,
    *,
    fill: str | None = None,
    outline: str | None = None,
    width: float = 1.0,
) -> list[int]:
    """在 canvas 上绘制圆角矩形（Tk 无圆角矩形图元：四直线 + 四角圆弧）。

    Args:
        canvas: 目标画布
        x0, y0, x1, y1: 外接矩形（画布坐标）
        radius: 圆角半径（自动钳制不超过边半长）
        fill: 填充色；None 表示不填充
        outline: 描边色；None 表示不描边
        width: 描边宽度（px）

    Returns:
        创建的全部图元 id（调用方可用 addtag_withtag 打标后整组重绘）
    """
    r = max(0.0, min(radius, (x1 - x0) / 2.0, (y1 - y0) / 2.0))
    items: list[int] = []
    if fill is not None:
        items.append(canvas.create_rectangle(x0 + r, y0, x1 - r, y1, fill=fill, outline=""))
        items.append(canvas.create_rectangle(x0, y0 + r, x1, y1 - r, fill=fill, outline=""))
    corners = (
        (x0, y0, 90),
        (x1 - 2 * r, y0, 0),
        (x1 - 2 * r, y1 - 2 * r, 270),
        (x0, y1 - 2 * r, 180),
    )
    if fill is not None:
        for ax0, ay0, start in corners:
            items.append(
                canvas.create_arc(
                    ax0,
                    ay0,
                    ax0 + 2 * r,
                    ay0 + 2 * r,
                    start=start,
                    extent=90,
                    style=tk.PIESLICE,
                    fill=fill,
                    outline="",
                )
            )
    if outline is not None:
        items.append(canvas.create_line(x0 + r, y0, x1 - r, y0, fill=outline, width=width))
        items.append(canvas.create_line(x1, y0 + r, x1, y1 - r, fill=outline, width=width))
        items.append(canvas.create_line(x1 - r, y1, x0 + r, y1, fill=outline, width=width))
        items.append(canvas.create_line(x0, y1 - r, x0, y0 + r, fill=outline, width=width))
        for ax0, ay0, start in corners:
            items.append(
                canvas.create_arc(
                    ax0,
                    ay0,
                    ax0 + 2 * r,
                    ay0 + 2 * r,
                    start=start,
                    extent=90,
                    style=tk.ARC,
                    outline=outline,
                    width=width,
                )
            )
    return items


def _surface_of(master: tk.Misc) -> str:
    """取父容器的底色作为 Canvas 自身底色（圆角四角外的区域用它填充）。

    Canvas 的 bg 与父容器一致时，圆角外的四角才真正"隐形"——否则露出
    系统默认白（SystemButtonFace），深色界面下四角发白（2026-10-14 实测）。
    ttk 容器无 bg 选项（取色于 style），兜底白色。
    """
    try:
        return str(master.cget("bg"))
    except (tk.TclError, AttributeError):
        return "#ffffff"


class RoundedCard(tk.Canvas):
    """圆角卡片容器：Canvas 画圆角底 + create_window 嵌内容 Frame。

    用法与旧 create_card 返回的 (card, inner) 兼容：
        card, inner = create_card(parent)   # theme 工厂
        card.pack(fill=tk.BOTH, expand=True)
        往 inner 里 pack 子控件

    高度策略：
    - 内容变高且当前高度装不下 → 长高；
    - 内容变矮且当前高度仍是我们设定的值（未被 pack 拉伸）→ 缩回；
    - 被 pack(fill/expand) 拉伸时高度归管理器，本类不干预。
    """

    def __init__(
        self,
        parent: tk.Misc,
        *,
        radius: int = RADIUS_CARD,
        bg: str = "#ffffff",
        surface: str = "#ffffff",
        border: str | None = None,
        border_width: float = 0.5,
        padx: int = 0,
        pady: int = 0,
        **kwargs: Any,
    ) -> None:
        kwargs.setdefault("width", 120)
        kwargs.setdefault("height", 40)
        super().__init__(parent, bg=surface, highlightthickness=0, bd=0, **kwargs)
        self._radius = float(radius)
        self._bg = bg
        self._border = border
        self._border_width = border_width
        self._set_height = 0

        # shell 为窗口奴隶，inner 承载调用方内容（inset = radius，见 K4）
        self._shell = tk.Frame(self, bg=bg)
        self._inner = tk.Frame(self._shell, bg=bg)
        self._inner.pack(fill=tk.BOTH, expand=True, padx=padx, pady=pady)
        self._win = self.create_window(self._radius, self._radius, window=self._shell, anchor=tk.NW)

        self.bind("<Configure>", self._on_canvas_configure)
        self._shell.bind("<Configure>", self._on_shell_configure)

    @property
    def inner(self) -> tk.Frame:
        """内容容器（调用方向其中 pack 子控件）。"""
        return self._inner

    def set_style(
        self,
        *,
        bg: str | None = None,
        border: str | None = None,
        border_width: float | None = None,
    ) -> None:
        """运行时换肤（OptionRow 状态切换用）：改填充/描边并重绘。

        同步 shell/inner 底色；子控件（Label/Canvas）的 bg 由调用方
        自行跟随更新（Tk 无级联换色）。
        """
        if bg is not None:
            self._bg = bg
            self._shell.configure(bg=bg)
            self._inner.configure(bg=bg)
        if border is not None:
            self._border = border
        if border_width is not None:
            self._border_width = border_width
        self._draw_bg()

    # ---------------------------------------------------------------- 绘制
    def _draw_bg(self) -> None:
        self.delete("bg")
        w = max(self.winfo_width(), 1)
        h = max(self.winfo_height(), 1)
        items = draw_round_rect(
            self,
            0,
            0,
            w,
            h,
            self._radius,
            fill=self._bg,
            outline=self._border,
            width=self._border_width,
        )
        for it in items:
            self.addtag_withtag("bg", it)

    def _sync_window_size(self) -> None:
        w = max(self.winfo_width() - 2 * self._radius, 1)
        h = max(self.winfo_height() - 2 * self._radius, 1)
        self.itemconfigure(self._win, width=w, height=h)

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self._draw_bg()
        self._sync_window_size()

    def _on_shell_configure(self, event: tk.Event) -> None:
        self.refit()

    def refit(self) -> None:
        """按内容自然高度重算自身高度（嵌套卡片联动的核心）。

        - 内容变高且当前装不下 → 长高；
        - 内容变矮且当前高度仍是我们设定的值（未被 pack 拉伸）→ 缩回；
        - 被 pack(fill/expand) 拉伸时高度归管理器，本类不干预；
        - 高度变化后向最近的祖先卡片冒泡 refit——嵌套卡片（选项行在
          选项卡内）的外层高度不随行高自动重算，必须显式传播，
          否则 pack 会把后排卡片挤瘪（2026-10-14 P2 实测根因）。
        """
        natural = int(self._shell.winfo_reqheight()) + int(2 * self._radius)
        current = self.winfo_height()
        changed = False
        if natural > current + 1:
            self._set_height = natural
            super().configure(height=natural)
            changed = True
        elif abs(natural - self._set_height) > 1 and abs(current - self._set_height) <= 1:
            self._set_height = natural
            super().configure(height=natural)
            changed = True
        if changed:
            self._bubble_refit()

    def _bubble_refit(self) -> None:
        """沿 master 链向上找最近的祖先 RoundedCard 并触发其 refit。"""
        w = self.master
        while isinstance(w, tk.Widget):
            if isinstance(w, RoundedCard):
                w.refit()
                return  # refit 内部会继续向上冒泡
            w = w.master


class RoundedButton(tk.Canvas):
    """圆角文字按钮（Canvas 绘制）。

    对齐旧 tk.Button 的常用 API 子集，兼容存量调用点：
    - pack/pack_forget/grid/destroy/focus_set/bind 继承自 Canvas
    - invoke() 触发 command
    - configure(text=/fg=/bg=/state=/activebackground=/font=/width=/cursor=)
      翻译为内部重绘（practice_panel / exam_mode / review_mode 等
      在运行时改按钮属性依赖此 shim）
    - takefocus + Return/Space 键盘激活（无障碍，对标 P0-7 模式）
    """

    def __init__(
        self,
        parent: tk.Misc,
        text: str = "",
        command: Callable[[], None] | None = None,
        *,
        font: Any = None,
        bg: str = "#1668dc",
        fg: str = "#ffffff",
        hover_bg: str | None = None,
        active_bg: str | None = None,
        disabled_bg: str = "#edf1f6",
        disabled_fg: str = "#98a2b3",
        radius: int = RADIUS_BTN,
        padx: int = 16,
        height: int = 32,
        width: int = 0,
        cursor: str = "hand2",
    ) -> None:
        super().__init__(
            parent,
            bg=_surface_of(parent),
            highlightthickness=0,
            bd=0,
            width=60,
            height=height,
            cursor=cursor,
        )
        self._text = text
        self._command = command
        self._font = _as_font_obj(font, self)
        self._bg = bg
        self._fg = fg
        self._hover_bg = hover_bg or bg
        self._active_bg = active_bg or bg
        self._disabled_bg = disabled_bg
        self._disabled_fg = disabled_fg
        self._radius = float(radius)
        self._padx = padx
        self._height = height
        self._width_chars = width
        self._enabled = True
        self._hover = False
        self._pressed = False

        self._text_item: int | None = None
        self._apply_geometry()

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Configure>", self._on_configure)
        self.configure(takefocus=True)
        self.bind("<Return>", self._on_return)
        self.bind("<space>", self._on_return)

    # ---------------------------------------------------------------- 几何
    def _measure_min_width(self) -> int:
        text_w = self._font.measure(self._text) if (self._font and self._text) else 0
        min_w = self._width_chars * 7 if self._width_chars > 0 else 0
        return max(int(text_w) + 2 * self._padx, min_w, self._height)

    def _apply_geometry(self) -> None:
        super().configure(width=self._measure_min_width(), height=self._height)
        self._redraw()

    # ---------------------------------------------------------------- 绘制
    def _current_colors(self) -> tuple[str, str]:
        if not self._enabled:
            return self._disabled_bg, self._disabled_fg
        if self._pressed:
            return self._active_bg, self._fg
        if self._hover:
            return self._hover_bg, self._fg
        return self._bg, self._fg

    def _redraw(self) -> None:
        self.delete("all")
        w = max(self.winfo_width(), 1)
        h = max(self.winfo_height(), 1)
        bg, fg = self._current_colors()
        draw_round_rect(self, 0, 0, w, h, self._radius, fill=bg)
        if self._text:
            self._text_item = self.create_text(
                w / 2, h / 2, text=self._text, fill=fg, font=self._font, anchor="center"
            )

    # ---------------------------------------------------------------- 事件
    def _on_configure(self, event: tk.Event) -> None:
        # 被管理器拉伸时保持文字居中（重绘代价小）
        self._redraw()

    def _on_enter(self, event: tk.Event) -> None:
        if self._enabled and not self._hover:
            self._hover = True
            self._redraw()

    def _on_leave(self, event: tk.Event) -> None:
        if self._hover or self._pressed:
            self._hover = False
            self._pressed = False
            if self._enabled:
                self._redraw()

    def _on_press(self, event: tk.Event) -> None:
        if self._enabled and not self._pressed:
            self._pressed = True
            self._redraw()
            self.focus_set()

    def _on_release(self, event: tk.Event) -> None:
        if not self._enabled:
            return
        was_pressed = self._pressed
        self._pressed = False
        self._redraw()
        if was_pressed:
            self.invoke()

    def _on_return(self, event: tk.Event) -> str:
        if self._enabled:
            self.invoke()
        return "break"

    # ---------------------------------------------------------------- API
    def invoke(self) -> None:
        """触发点击（禁用态无操作，对齐 tk.Button 语义）。"""
        if not self._enabled:
            return
        if self._command is not None:
            self._command()

    def cget(self, key: str) -> Any:
        """兼容 shim：text/state/bg/fg/activebackground/font 读内部状态。

        Canvas 无 -text/-state 选项，存量代码与测试经 cget 读按钮属性
        （如 exam_mode.start_btn.cget("state")、review 收藏按钮文案），
        在此翻译；其余选项透传 Canvas。
        """
        k = str(key)
        if k == "text":
            return self._text
        if k == "state":
            return tk.DISABLED if not self._enabled else tk.NORMAL
        if k in ("bg", "background"):
            return self._bg
        if k in ("fg", "foreground"):
            return self._fg
        if k == "activebackground":
            return self._active_bg
        if k == "font":
            return self._font
        return super().cget(key)

    def configure(self, cnfin: Any = None, **kwargs: Any) -> None:  # type: ignore[override]
        """兼容 shim：text/fg/bg/state/activebackground/font/width/cursor 翻译为重绘。"""
        if cnfin is not None and isinstance(cnfin, dict):
            kwargs = {**cnfin, **kwargs}
        text = kwargs.pop("text", None)
        fg = kwargs.pop("fg", None)
        if fg is None:
            fg = kwargs.pop("foreground", None)
        else:
            kwargs.pop("foreground", None)
        bg = kwargs.pop("bg", None)
        if bg is None:
            bg = kwargs.pop("background", None)
        else:
            kwargs.pop("background", None)
        active_bg = kwargs.pop("activebackground", None)
        font = kwargs.pop("font", None)
        width = kwargs.pop("width", None)
        state = kwargs.pop("state", None)
        cursor = kwargs.pop("cursor", None)

        if text is not None:
            self._text = str(text)
        if fg is not None:
            self._fg = fg
        if bg is not None:
            self._bg = bg
            self._hover_bg = active_bg if active_bg is not None else bg
            self._active_bg = active_bg if active_bg is not None else bg
        elif active_bg is not None:
            self._active_bg = active_bg
        if font is not None:
            self._font = font
        if width is not None:
            self._width_chars = int(width)
        if cursor is not None:
            super().configure(cursor=cursor)
        if state is not None:
            self._enabled = str(state) != str(tk.DISABLED)
        super().configure(**kwargs)
        self._apply_geometry()


class Switch(tk.Canvas):
    """圆角开关（Canvas 绘制，替代 tk.Checkbutton 的现代形态）。

    绑定 BooleanVar；切换时触发 command；滑块位移两帧补间。
    """

    def __init__(
        self,
        parent: tk.Misc,
        variable: tk.BooleanVar | None = None,
        command: Callable[[], None] | None = None,
        *,
        on_bg: str = "#1668dc",
        off_bg: str = "#d7dee8",
        knob_color: str = "#ffffff",
        width: int = SWITCH_WIDTH,
        height: int = SWITCH_HEIGHT,
    ) -> None:
        super().__init__(
            parent,
            bg=_surface_of(parent),
            highlightthickness=0,
            bd=0,
            width=width,
            height=height,
            cursor="hand2",
        )
        self._var = variable if variable is not None else tk.BooleanVar(value=False)
        self._command = command
        self._on_bg = on_bg
        self._off_bg = off_bg
        self._knob_color = knob_color
        # 注意：禁名 self._w/_h——tkinter BaseWidget 用 _w 存 Tcl 路径名，覆盖即毁控件
        self._track_w = width
        self._track_h = height
        self._anim_ids: set[str] = set()
        self._knob_x = self._knob_on_x() if self._var.get() else self._knob_off_x()
        self._draw()
        self._var.trace_add("write", self._on_var_write)
        self.bind("<Button-1>", self._on_click)
        self.configure(takefocus=True)
        self.bind("<Return>", self._on_click)
        self.bind("<space>", self._on_click)

    # ---------------------------------------------------------------- 几何
    def _knob_radius(self) -> float:
        return self._track_h / 2.0 - 2.5

    def _knob_off_x(self) -> float:
        return self._track_h / 2.0

    def _knob_on_x(self) -> float:
        return self._track_w - self._track_h / 2.0

    def _draw(self) -> None:
        self.delete("all")
        on = self._var.get()
        draw_round_rect(
            self,
            0,
            0,
            self._track_w,
            self._track_h,
            self._track_h / 2.0,
            fill=self._on_bg if on else self._off_bg,
        )
        r = self._knob_radius()
        self.create_oval(
            self._knob_x - r,
            self._track_h / 2.0 - r,
            self._knob_x + r,
            self._track_h / 2.0 + r,
            fill=self._knob_color,
            outline="",
        )

    # ---------------------------------------------------------------- 交互
    def _on_click(self, event: tk.Event | None = None) -> str:
        self.toggle()
        return "break"

    def _on_var_write(self, *_args: Any) -> None:
        self._animate_to(self._knob_on_x() if self._var.get() else self._knob_off_x())

    def _animate_to(self, target: float) -> None:
        self._cancel_anim()
        start = self._knob_x
        for step in range(1, SWITCH_ANIM_STEPS + 1):
            delay = SWITCH_ANIM_INTERVAL_MS * step
            mid = start + (target - start) * step / SWITCH_ANIM_STEPS

            def _frame(m: float = mid) -> None:
                self._apply_anim(m)

            job_id = self.after(delay, _frame)
            self._anim_ids.add(job_id)

    def _apply_anim(self, mid: float) -> None:
        try:
            self._knob_x = mid
            self._draw()
        except tk.TclError:
            logger.debug("Switch 动画帧触发时控件已销毁")

    def _cancel_anim(self) -> None:
        for job_id in list(self._anim_ids):
            try:
                self.after_cancel(job_id)
            except tk.TclError:
                pass  # 任务已执行或控件已销毁
        self._anim_ids.clear()

    # ---------------------------------------------------------------- API
    def toggle(self) -> None:
        self._var.set(not self._var.get())
        if self._command is not None:
            self._command()

    def get(self) -> bool:
        return bool(self._var.get())

    def set(self, value: bool) -> None:
        self._var.set(bool(value))

    def destroy(self) -> None:
        self._cancel_anim()
        super().destroy()


class IconButton(tk.Canvas):
    """图标按钮（Canvas 绘制，主题切换等纯图标操作用）。

    对齐 RoundedButton 的 API 子集：invoke() / configure(icon=/fg=/bg=) /
    takefocus + Return/Space 键盘激活。
    """

    def __init__(
        self,
        parent: tk.Misc,
        icon: str,
        command: Callable[[], None] | None = None,
        *,
        size: int = 28,
        bg: str = "#1c2637",
        hover_bg: str | None = None,
        fg: str = "#e8edf5",
        radius: int = 8,
        icon_size: int = 16,
    ) -> None:
        super().__init__(
            parent,
            bg=_surface_of(parent),
            highlightthickness=0,
            bd=0,
            width=size,
            height=size,
            cursor="hand2",
        )
        self._icon = icon
        self._command = command
        self._bg = bg
        self._hover_bg = hover_bg or bg
        self._fg = fg
        self._radius = float(radius)
        self._size = size
        self._icon_size = icon_size
        self._hover = False
        self._draw()

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self.configure(takefocus=True)
        self.bind("<Return>", self._on_return)
        self.bind("<space>", self._on_return)

    def _draw(self) -> None:
        from .icons import draw_icon

        self.delete("all")
        draw_round_rect(
            self,
            0,
            0,
            self._size,
            self._size,
            self._radius,
            fill=self._hover_bg if self._hover else self._bg,
        )
        draw_icon(self, self._icon, self._size / 2, self._size / 2, self._icon_size, self._fg)

    def _on_enter(self, event: tk.Event) -> None:
        self._hover = True
        self._draw()

    def _on_leave(self, event: tk.Event) -> None:
        self._hover = False
        self._draw()

    def _on_click(self, event: tk.Event) -> None:
        self.focus_set()
        self.invoke()

    def _on_return(self, event: tk.Event) -> str:
        self.invoke()
        return "break"

    def invoke(self) -> None:
        if self._command is not None:
            self._command()

    def configure(self, cnfin: Any = None, **kwargs: Any) -> None:  # type: ignore[override]
        if cnfin is not None and isinstance(cnfin, dict):
            kwargs = {**cnfin, **kwargs}
        icon = kwargs.pop("icon", None)
        fg = kwargs.pop("fg", None)
        bg = kwargs.pop("bg", None)
        if icon is not None:
            self._icon = str(icon)
        if fg is not None:
            self._fg = fg
        if bg is not None:
            self._bg = bg
        super().configure(**kwargs)
        self._draw()


class Chip(tk.Canvas):
    """小胶囊标签（题型 / 统计 / 状态提示）。

    宽度随文字自适应；configure(text=/fg=/bg=) 支持运行时更新。
    """

    def __init__(
        self,
        parent: tk.Misc,
        text: str = "",
        *,
        font: Any = None,
        bg: str = "#e8f1fc",
        fg: str = "#1668dc",
        radius: int = RADIUS_CHIP,
        padx: int = 10,
        height: int = 20,
    ) -> None:
        super().__init__(
            parent, bg=_surface_of(parent), highlightthickness=0, bd=0, width=40, height=height
        )
        self._text = text
        self._font = _as_font_obj(font, self)
        self._bg = bg
        self._fg = fg
        self._radius = float(radius)
        self._padx = padx
        self._height = height
        self._apply()
        self.bind("<Configure>", self._on_configure)

    def _apply(self) -> None:
        text_w = self._font.measure(self._text) if (self._font and self._text) else 0
        super().configure(
            width=max(int(text_w) + 2 * self._padx, self._height), height=self._height
        )
        self._redraw()

    def _redraw(self) -> None:
        self.delete("all")
        w = max(self.winfo_width(), 1)
        h = max(self.winfo_height(), 1)
        draw_round_rect(self, 0, 0, w, h, self._radius, fill=self._bg)
        if self._text:
            self.create_text(
                w / 2, h / 2, text=self._text, fill=self._fg, font=self._font, anchor="center"
            )

    def _on_configure(self, event: tk.Event) -> None:
        self._redraw()

    def cget(self, key: str) -> Any:
        """兼容 shim：text/fg/bg 读内部状态（如考试倒计时测试断言 cget）。"""
        k = str(key)
        if k == "text":
            return self._text
        if k in ("fg", "foreground"):
            return self._fg
        if k in ("bg", "background"):
            return self._bg
        return super().cget(key)

    def configure(self, cnfin: Any = None, **kwargs: Any) -> None:  # type: ignore[override]
        if cnfin is not None and isinstance(cnfin, dict):
            kwargs = {**cnfin, **kwargs}
        text = kwargs.pop("text", None)
        fg = kwargs.pop("fg", None)
        bg = kwargs.pop("bg", None)
        font = kwargs.pop("font", None)
        if text is not None:
            self._text = str(text)
        if fg is not None:
            self._fg = fg
        if bg is not None:
            self._bg = bg
        if font is not None:
            self._font = font
        super().configure(**kwargs)
        self._apply()
