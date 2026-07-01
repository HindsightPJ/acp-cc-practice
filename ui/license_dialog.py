"""注册码输入对话框组件。"""

import tkinter as tk
from tkinter import messagebox
from typing import Optional, Callable, Tuple

from license import LicenseStatus
from license.verifier import verify, LicenseVerifier
from .theme import Theme, font_ui, font_ui_semibold, font_mono

theme = Theme()


_LICENSE_ERROR_MESSAGES = {
    None: "授权失败，请检查注册码。",
    "invalid_signature": "注册码无效，请联系作者。",
    "wrong_machine": "注册码不属于本机，请确认机器码后重新申请。",
    "corrupt_questions": "题库密文损坏，请联系作者。",
    "corrupt_license": "注册码文件损坏。",
}


def _get_license_error_message(err) -> str:
    """根据 LicenseError 枚举返回用户可读消息。"""
    err_key = err.value if err else None
    return _LICENSE_ERROR_MESSAGES.get(err_key, "授权失败。")


def _verify_and_save_license(code: str, license_dir: str) -> Tuple[bool, str, bool]:
    """验证注册码并持久化。

    Args:
        code: 用户输入的注册码
        license_dir: license.dat 保存目录

    Returns:
        (success, message, should_close_dialog)
    """
    status, k, err = verify(code)
    if status == LicenseStatus.AUTHORIZED and k:
        verifier = LicenseVerifier(data_dir=license_dir)
        if verifier.save_license(code):
            return (True, "授权成功！请重启程序加载完整题库。", True)
        return (False, "注册码验证成功，但保存到本地失败。\n请检查程序目录写入权限。", False)
    return (False, _get_license_error_message(err), False)


class LicenseDialog:
    """注册码输入对话框。

    负责 UI 构建与验证交互；验证逻辑委托给传入的 verify_and_save callback。
    """

    def __init__(
        self,
        parent,
        license_dir: str,
        verify_and_save: Optional[Callable[[str, str], Tuple[bool, str, bool]]] = None,
    ) -> None:
        """初始化对话框。

        Args:
            parent: 父窗口
            license_dir: license.dat 保存目录
            verify_and_save: 可选自定义验证回调，签名为 (code, license_dir) -> (success, message, should_close)
        """
        self.parent = parent
        self.license_dir = license_dir
        self.verify_and_save = verify_and_save or _verify_and_save_license
        self.dialog: Optional[tk.Toplevel] = None
        self._license_entry: Optional[tk.Text] = None

    def show(self) -> bool:
        """显示对话框；若无法读取机器码则报错并返回 False。"""
        from license.fingerprint import get_machine_code_or_none

        machine_code = get_machine_code_or_none()
        if machine_code is None:
            messagebox.showerror("错误", "无法读取本机机器码，授权仅支持 Windows。")
            return False

        self._build_dialog(machine_code)
        return True

    def _build_dialog(self, machine_code: str) -> None:
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("输入注册码")
        self.dialog.geometry("500x420")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()

        # 机器码显示
        tk.Label(
            self.dialog,
            text="本机机器码：",
            font=font_ui_semibold(11),
            fg=theme.TEXT_PRIMARY,
            bg=theme.BG_PAGE,
        ).pack(anchor="w", padx=15, pady=(15, 5))
        code_entry = tk.Text(
            self.dialog,
            height=3,
            wrap="char",
            font=font_mono(9),
            bg=theme.BG_INPUT,
            fg=theme.TEXT_PRIMARY,
            relief="flat",
            bd=0,
            highlightbackground=theme.BORDER,
            highlightthickness=1,
        )
        code_entry.insert("1.0", machine_code)
        code_entry.config(state="disabled")
        code_entry.pack(fill="x", padx=15, pady=(0, 10))

        tk.Label(
            self.dialog,
            text="把此机器码发给作者，收到注册码后粘贴到下方：",
            font=font_ui(9),
            fg=theme.TEXT_MUTED,
            bg=theme.BG_PAGE,
        ).pack(anchor="w", padx=15)

        # 注册码输入框
        self._license_entry = tk.Text(
            self.dialog,
            height=8,
            wrap="char",
            font=font_mono(9),
            bg=theme.BG_INPUT,
            fg=theme.TEXT_PRIMARY,
            relief="flat",
            bd=0,
            highlightbackground=theme.BORDER,
            highlightthickness=1,
        )
        self._license_entry.pack(fill="both", expand=True, padx=15, pady=10)

        btn_frame = tk.Frame(self.dialog, bg=theme.BG_PAGE)
        btn_frame.pack(fill="x", padx=15, pady=(0, 15))
        tk.Button(
            btn_frame,
            text="验证",
            command=self._on_verify,
            bg=theme.ACCENT,
            fg="white",
            relief="flat",
            padx=20,
            cursor="hand2",
            activebackground=theme.ACCENT_HOVER,
            activeforeground="white",
        ).pack(side="right")
        tk.Button(
            btn_frame,
            text="取消",
            command=self.close,
            relief="flat",
            padx=20,
            bg=theme.BTN_NORMAL,
            fg=theme.BTN_NORMAL_FG,
            cursor="hand2",
        ).pack(side="right", padx=5)

    def _on_verify(self) -> None:
        if self._license_entry is None or self.dialog is None:
            return
        code = self._license_entry.get("1.0", "end").strip()
        if not code:
            messagebox.showwarning("提示", "请输入注册码", parent=self.dialog)
            return
        success, message, should_close = self.verify_and_save(code, self.license_dir)
        if success:
            messagebox.showinfo("成功", message, parent=self.dialog)
        else:
            messagebox.showerror("失败", message, parent=self.dialog)
        if should_close:
            self.close()

    def close(self) -> None:
        """关闭对话框。"""
        if self.dialog is not None:
            try:
                self.dialog.destroy()
            except tk.TclError:
                pass
            self.dialog = None
