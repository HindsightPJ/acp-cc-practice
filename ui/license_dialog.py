"""注册码输入对话框组件。"""

import queue
import threading
import tkinter as tk
from tkinter import messagebox
from typing import Callable

from license import LicenseStatus
from license.verifier import verify, LicenseVerifier
from .theme import theme, font_ui, font_ui_semibold, font_mono
from .base_dialog import BaseDialog


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


def _verify_and_save_license(
    code: str, license_dir: str, machine_code: str | None = None
) -> tuple[bool, str, bool]:
    """验证注册码并持久化。

    Args:
        code: 用户输入的注册码
        license_dir: license.dat 保存目录
        machine_code: 可选的本机机器码。传入时直接复用，避免 verify() 内部
            再次启动 PowerShell 子进程采集（耗时 0.2~5 秒）。

    Returns:
        (success, message, should_close_dialog)
    """
    status, k, err = verify(code, machine_code=machine_code)
    if status == LicenseStatus.AUTHORIZED and k:
        verifier = LicenseVerifier(data_dir=license_dir)
        if verifier.save_license(code):
            return (True, "授权成功！请重启程序加载完整题库。", True)
        return (False, "注册码验证成功，但保存到本地失败。\n请检查程序目录写入权限。", False)
    return (False, _get_license_error_message(err), False)


class LicenseDialog(BaseDialog):
    """注册码输入对话框。

    负责UI 构建与验证交互；验证逻辑委托给传入的 verify_and_save callback。
    """

    def __init__(
        self,
        parent,
        license_dir: str,
        verify_and_save: Callable[[str, str, str | None], tuple[bool, str, bool]] | None = None,
    ) -> None:
        """初始化对话框。

        Args:
            parent: 父窗口
            license_dir: license.dat 保存目录
            verify_and_save: 可选自定义验证回调，签名为
                (code, license_dir, machine_code) -> (success, message, should_close)
        """
        super().__init__(parent, title="输入注册码", size="500x420")
        self.license_dir = license_dir
        self.verify_and_save = verify_and_save or _verify_and_save_license
        self._license_entry: tk.Text | None = None
        # P2-6: 保存验证按钮引用，异步验证期间禁用避免重复点击
        self._verify_btn: tk.Button | None = None
        # P2-6: 子线程与主线程之间的结果传递通道
        self._verify_queue: queue.Queue = queue.Queue()
        # P0-2: 缓存 show() 时采集的机器码，_on_verify 时复用，
        # 避免 verify() 内部再次启动 PowerShell 子进程采集（耗时 0.2~5 秒）。
        self._machine_code: str | None = None

    def show(self) -> bool:
        """显示对话框；若无法读取机器码则报错并返回 False。"""
        from license.fingerprint import get_machine_code_or_none

        machine_code = get_machine_code_or_none()
        if machine_code is None:
            messagebox.showerror("错误", "无法读取本机机器码，授权仅支持 Windows。")
            return False

        # 缓存机器码供 _on_verify 复用，避免验证时再次采集
        self._machine_code = machine_code
        self._create_dialog()
        self._build_content(machine_code)
        return True

    def _build_content(self, machine_code: str) -> None:
        assert self.dialog is not None

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
        # P2-6: 保存验证按钮引用，异步验证期间禁用避免重复点击
        self._verify_btn = tk.Button(
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
        )
        self._verify_btn.pack(side="right")
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

        # P2-6: 异步执行 PBKDF2（60 万次迭代，0.3-1 秒），
        # 避免在主线程中执行导致 UI 冻结。期间禁用验证按钮防止重复提交。
        if self._verify_btn is not None:
            self._verify_btn.configure(state=tk.DISABLED, text="验证中...")

        machine_code = self._machine_code
        license_dir = self.license_dir
        verify_fn = self.verify_and_save
        result_queue = self._verify_queue

        def worker() -> None:
            try:
                result = verify_fn(code, license_dir, machine_code)
            except Exception as exc:  # noqa: BLE001 - 兜底，确保结果能回传主线程
                result = (False, f"验证过程出错: {exc}", False)
            result_queue.put(result)

        threading.Thread(target=worker, daemon=True).start()
        # 主线程轮询 queue，避免子线程直接调用 tkinter（非线程安全）
        self._poll_verify_result()

    def _poll_verify_result(self) -> None:
        """轮询验证结果 queue（在主线程中执行）。"""
        if self.dialog is None:
            return  # dialog 已关闭，停止轮询
        try:
            result = self._verify_queue.get_nowait()
        except queue.Empty:
            self.dialog.after(100, self._poll_verify_result)
            return
        self._on_verify_done(result)

    def _on_verify_done(self, result: tuple[bool, str, bool]) -> None:
        """子线程完成后的回调（在主线程中执行）。

        Args:
            result: (success, message, should_close)
        """
        success, message, should_close = result
        # dialog 可能在异步期间被用户关闭，此时无需再弹窗
        if self.dialog is None:
            return
        # 恢复按钮状态
        if self._verify_btn is not None:
            self._verify_btn.configure(state=tk.NORMAL, text="验证")
        if success:
            messagebox.showinfo("成功", message, parent=self.dialog)
        else:
            messagebox.showerror("失败", message, parent=self.dialog)
        if should_close:
            self.close()
