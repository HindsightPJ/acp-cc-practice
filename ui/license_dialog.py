"""注册码输入对话框（QDialog 版）。

验证交互职责：机器码只读展示 + 注册码输入 + 异步验证（PBKDF2 60 万次
迭代 0.3~1s，子线程执行防 UI 冻结，queue 回传主线程轮询）。
验证逻辑委托 _verify_and_save_license（可注入替换，测试用）。
"""

import queue
import threading
from typing import Callable

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from license import LicenseError, LicenseStatus
from license.verifier import verify, LicenseVerifier
from .base_dialog import BaseDialog

_LICENSE_ERROR_MESSAGES = {
    None: "授权失败，请检查注册码。",
    "invalid_signature": "注册码无效，请联系作者。",
    "wrong_machine": "注册码不属于本机，请确认机器码后重新申请。",
    "corrupt_questions": "题库密文损坏，请联系作者。",
    "corrupt_license": "注册码文件损坏。",
}

# 结果轮询间隔（毫秒）
_POLL_INTERVAL_MS = 100


def _get_license_error_message(err: LicenseError | None) -> str:
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

    Args:
        parent: 父窗口
        license_dir: license.dat 保存目录
        machine_code: 预采集的机器码（调用方先 get_machine_code_or_none，
            None 时不应实例化本对话框）
        verify_and_save: 可选自定义验证回调，签名
            (code, license_dir, machine_code) -> (success, message, should_close)
    """

    def __init__(
        self,
        parent: QWidget | None,
        license_dir: str,
        machine_code: str,
        verify_and_save: Callable[[str, str, str | None], tuple[bool, str, bool]] | None = None,
    ) -> None:
        super().__init__(parent, title="输入注册码", width=460, height=380)
        self.license_dir = license_dir
        self.verify_and_save = verify_and_save or _verify_and_save_license
        self._machine_code = machine_code
        self._verify_queue: "queue.Queue[tuple[bool, str, bool]]" = queue.Queue()

        # 结果轮询定时器：父控件为对话框，关闭随 QObject 树释放（L1 资源红线）
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(_POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll_verify_result)

        self._build_ui()

    # -------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 22, 24, 20)
        v.setSpacing(10)

        title = QLabel("本机机器码")
        title.setProperty("qMeta", True)
        v.addWidget(title)

        code_view = QPlainTextEdit(self._machine_code)
        code_view.setReadOnly(True)
        code_view.setFixedHeight(52)
        v.addWidget(code_view)

        hint = QLabel("把此机器码发给作者，收到注册码后粘贴到下方：")
        hint.setProperty("qMeta", True)
        v.addWidget(hint)

        self._license_entry = QPlainTextEdit()
        self._license_entry.setPlaceholderText("粘贴注册码 ...")
        v.addWidget(self._license_entry, 1)

        # 规则线分段（F 语言）
        line = QFrame()
        line.setObjectName("qline")
        v.addWidget(line)

        bh = QHBoxLayout()
        bh.setSpacing(0)
        self._verify_btn = QPushButton("验证")
        self._verify_btn.setObjectName("goBtn")
        self._verify_btn.clicked.connect(self._on_verify)
        bh.addWidget(self._verify_btn, 2)
        cancel_btn = QPushButton("取消")
        cancel_btn.setProperty("actBtn", True)
        cancel_btn.clicked.connect(self.reject)
        bh.addWidget(cancel_btn, 1)
        v.addLayout(bh)

    # -------------------------------------------------------------- 验证
    def _on_verify(self) -> None:
        code = self._license_entry.toPlainText().strip()
        if not code:
            QMessageBox.warning(self, "提示", "请输入注册码")
            return

        # 异步执行 PBKDF2（60 万次迭代 0.3~1s），期间禁用按钮防重复提交
        self._verify_btn.setEnabled(False)
        self._verify_btn.setText("验证中 ...")

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

        threading.Thread(target=worker, daemon=True, name="license-verify").start()
        self._poll_timer.start()

    def _poll_verify_result(self) -> None:
        """主线程轮询验证结果 queue（子线程禁直接操作 UI）。"""
        try:
            result = self._verify_queue.get_nowait()
        except queue.Empty:
            return
        self._poll_timer.stop()
        self._on_verify_done(result)

    def _on_verify_done(self, result: tuple[bool, str, bool]) -> None:
        """验证完成回调（主线程）。"""
        success, message, should_close = result
        self._verify_btn.setEnabled(True)
        self._verify_btn.setText("验证")
        if success:
            QMessageBox.information(self, "成功", message)
        else:
            QMessageBox.critical(self, "失败", message)
        if should_close:
            self.accept()

    # -------------------------------------------------------------- 工厂
    @staticmethod
    def open_for(
        parent: QWidget | None,
        license_dir: str,
        verify_and_save: Callable[[str, str, str | None], tuple[bool, str, bool]] | None = None,
    ) -> bool:
        """采集机器码并模态显示对话框；返回授权流程是否成功完成。

        机器码读取失败（非 Windows 等）时报错并返回 False。
        命名避讳 QWidget.create（Qt 原生窗口创建方法，撞名会触发 mypy override 冲突）。
        """
        from license.fingerprint import get_machine_code_or_none

        machine_code = get_machine_code_or_none()
        if machine_code is None:
            QMessageBox.critical(parent, "错误", "无法读取本机机器码，授权仅支持 Windows。")
            return False
        dialog = LicenseDialog(parent, license_dir, machine_code, verify_and_save)
        dialog.exec()
        return dialog.result() == QDialog.DialogCode.Accepted
