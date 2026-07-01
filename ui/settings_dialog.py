"""设置对话框组件（TD-34）。

提供语言切换与暗色模式开关；修改保存后提示用户重启生效。
"""

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional, Callable, Dict

from .theme import Theme, font_ui, font_ui_semibold
from .i18n import _, get_supported_languages, get_language, set_language
from app_state import AppState

theme = Theme()


class SettingsDialog:
    """设置对话框。

    允许用户切换界面语言与暗色模式；所有变更通过 AppState 持久化。
    由于 tkinter 已创建组件不会自动响应主题变更，当前实现保存设置后
    提示用户重启生效。
    """

    def __init__(
        self,
        parent,
        app_state: AppState,
        on_settings_saved: Optional[Callable[[Dict[str, object]], None]] = None,
    ) -> None:
        """初始化对话框。

        Args:
            parent: 父窗口
            app_state: 应用状态对象，用于读写设置
            on_settings_saved: 设置保存后的回调，接收保存的设置字典
        """
        self.parent = parent
        self.app_state = app_state
        self.on_settings_saved = on_settings_saved
        self.dialog: Optional[tk.Toplevel] = None
        self._lang_var: Optional[tk.StringVar] = None
        self._dark_var: Optional[tk.BooleanVar] = None

    def show(self) -> None:
        """显示设置对话框。"""
        self._build_dialog()

    def _build_dialog(self) -> None:
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title(_("settings"))
        self.dialog.geometry("420x260")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        self.dialog.configure(bg=theme.BG_PAGE)

        # 标题
        tk.Label(
            self.dialog,
            text=_("settings"),
            font=font_ui_semibold(14),
            fg=theme.TEXT_PRIMARY,
            bg=theme.BG_PAGE,
        ).pack(anchor="w", padx=20, pady=(20, 16))

        # 语言选择
        lang_frame = tk.Frame(self.dialog, bg=theme.BG_PAGE)
        lang_frame.pack(fill="x", padx=20, pady=(0, 12))
        tk.Label(
            lang_frame,
            text=_("language"),
            font=font_ui(11),
            fg=theme.TEXT_PRIMARY,
            bg=theme.BG_PAGE,
            width=10,
            anchor="w",
        ).pack(side=tk.LEFT)

        self._lang_var = tk.StringVar(value=get_language())
        lang_combo = ttk.Combobox(
            lang_frame,
            textvariable=self._lang_var,
            values=get_supported_languages(),
            state="readonly",
            width=12,
        )
        lang_combo.pack(side=tk.LEFT, padx=(8, 0))

        # 暗色模式开关
        dark_frame = tk.Frame(self.dialog, bg=theme.BG_PAGE)
        dark_frame.pack(fill="x", padx=20, pady=(0, 12))
        tk.Label(
            dark_frame,
            text=_("dark_mode"),
            font=font_ui(11),
            fg=theme.TEXT_PRIMARY,
            bg=theme.BG_PAGE,
            width=10,
            anchor="w",
        ).pack(side=tk.LEFT)

        self._dark_var = tk.BooleanVar(value=theme.is_dark_mode())
        dark_check = tk.Checkbutton(
            dark_frame,
            variable=self._dark_var,
            bg=theme.BG_PAGE,
            activebackground=theme.BG_PAGE,
            selectcolor=theme.BG_CARD,
        )
        dark_check.pack(side=tk.LEFT, padx=(8, 0))

        # 提示文本
        tk.Label(
            self.dialog,
            text=_("restart_to_apply"),
            font=font_ui(9),
            fg=theme.TEXT_MUTED,
            bg=theme.BG_PAGE,
        ).pack(anchor="w", padx=20, pady=(4, 0))

        # 按钮
        btn_frame = tk.Frame(self.dialog, bg=theme.BG_PAGE)
        btn_frame.pack(fill="x", padx=20, pady=(20, 0))
        tk.Button(
            btn_frame,
            text=_("ok"),
            command=self._on_ok,
            bg=theme.ACCENT,
            fg="white",
            relief="flat",
            padx=20,
            cursor="hand2",
            activebackground=theme.ACCENT_HOVER,
            activeforeground="white",
        ).pack(side=tk.RIGHT)
        tk.Button(
            btn_frame,
            text=_("cancel"),
            command=self.close,
            relief="flat",
            padx=20,
            bg=theme.BTN_NORMAL,
            fg=theme.BTN_NORMAL_FG,
            cursor="hand2",
        ).pack(side=tk.RIGHT, padx=5)

    def _on_ok(self) -> None:
        """保存设置并关闭对话框。"""
        if self._lang_var is None or self._dark_var is None or self.dialog is None:
            return

        new_lang = self._lang_var.get()
        new_dark = self._dark_var.get()

        set_language(new_lang)
        theme.set_dark_mode(new_dark)

        self.app_state.set_setting("language", new_lang)
        self.app_state.set_setting("dark_mode", new_dark)
        self.app_state.save()

        saved_settings = {"language": new_lang, "dark_mode": new_dark}
        if self.on_settings_saved:
            self.on_settings_saved(saved_settings)

        messagebox.showinfo(_("settings"), _("restart_to_apply"), parent=self.dialog)
        self.close()

    def close(self) -> None:
        """关闭对话框。"""
        if self.dialog is not None:
            try:
                self.dialog.destroy()
            except tk.TclError:
                pass
            self.dialog = None
