"""应用装配：QApplication + Frameless splash + 后台加载题库/授权 → MainWindow。

装配顺序（desktop_python.md §三）：
1. 解析目录 + 日志
2. QApplication（Qt 一切控件的前提）
3. 读进度取主题模式 → 应用全局 QSS（splash 与主窗口同主题，无闪变）
4. Frameless splash（同 F 方案站牌语言，QSS 类复用，无散写颜色）
5. 后台线程跑 license 验证 + 题库解密（0.5~6s），结果经 queue 回主线程
6. QTimer 轮询 queue：成功 → MainWindow；失败 → QMessageBox.critical 后退出
"""

from __future__ import annotations

import logging
import os
import queue
import sys
import threading
from dataclasses import dataclass
from typing import Any, cast

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QVBoxLayout, QWidget

from data_manager import DataManager, DataLoadError
from license import LicenseStatus
from license.verifier import LicenseVerifier
from logging_utils import configure_app_logging, log_error
from models import Question
from ui.main_window import MainWindow
from ui.theme import apply_qss, center_window
from ui.titlebar import BRAND_TEXT
from app_state import AppState


def _resolve_base_dir() -> str:
    """PyInstaller 打包后从 _MEIPASS 读取只读 data 文件；开发模式从源码目录读取。"""
    if hasattr(sys, "_MEIPASS"):
        return cast(str, sys._MEIPASS)
    return os.path.dirname(os.path.abspath(__file__))


def _resolve_user_data_dir() -> str:
    """用户可写数据目录：打包后 = exe同级/data/；开发模式 = 源码/data/。

    progress.json / license.dat / app.log 都写到此处。
    打包后 _MEIPASS 是临时解包目录，每次启动都不同，不能用于持久化。
    """
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        user_data_dir = os.path.join(exe_dir, "data")
        os.makedirs(user_data_dir, exist_ok=True)
        return user_data_dir
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _setup_logging(user_data_dir: str) -> None:
    """配置 logging 到 user_data_dir/app.log，启用轮转避免日志无限增长。"""
    log_file = os.path.join(user_data_dir, "app.log")
    configure_app_logging(log_file, level=logging.WARNING)


@dataclass
class LoadSuccess:
    """后台线程加载成功的结果。"""

    status: LicenseStatus
    license_failed: bool
    questions: list[Question]
    meta: dict[str, Any] | None


@dataclass
class LoadFailure:
    """后台线程加载失败的结果。"""

    message: str
    mode: str = "unknown"


def _load_app_data_async(
    data_manager: DataManager,
    verifier: LicenseVerifier,
    result_queue: "queue.Queue[LoadSuccess | LoadFailure]",
) -> None:
    """后台线程：执行 license 验证 + 题库加载，结果放入 queue。

    PowerShell 子进程（0.2~5s）+ PBKDF2 60 万次迭代（0.3~1s）+ Fernet 解密
    （50~300ms）全部在后台线程执行，UI 立即显示 splash。
    """
    try:
        status, key, license_failed = verifier.check_local_license()
        try:
            if status == LicenseStatus.AUTHORIZED and key:
                questions = data_manager.load_full_questions(key)
            else:
                questions = data_manager.load_trial_questions()
        except DataLoadError as e:
            mode = "trial" if status != LicenseStatus.AUTHORIZED else "unknown"
            result_queue.put(LoadFailure(str(e), mode))
            return

        meta = data_manager.load_meta()
        result_queue.put(LoadSuccess(status, license_failed, questions, meta))
    except Exception as e:  # noqa: BLE001 - desktop_python.md §二.3：后台线程兜底必须经 queue 传回主线程
        # 兜底：任何未预期异常都通过 queue 传回主线程，避免线程静默退出
        result_queue.put(LoadFailure(f"加载失败: {e}", "unknown"))


def _build_splash(app: QApplication, theme_mode: str) -> QWidget:
    """Frameless 站牌语言 splash：brand + 加载文案，全部走 QSS 语义类。"""
    apply_qss(app, theme_mode)
    splash = QWidget()
    splash.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
    splash.setFixedSize(320, 160)
    v = QVBoxLayout(splash)
    v.addStretch(1)
    brand = QLabel(BRAND_TEXT)
    brand.setObjectName("brand")
    brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
    v.addWidget(brand)
    hint = QLabel("正在加载题库 ...")
    hint.setObjectName("subTitle")
    hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
    v.addWidget(hint)
    v.addStretch(1)
    center_window(splash)
    return splash


def main() -> None:
    base_dir = _resolve_base_dir()
    user_data_dir = _resolve_user_data_dir()
    _setup_logging(user_data_dir)
    logger = logging.getLogger(__name__)

    data_manager = DataManager(base_dir, user_data_dir=user_data_dir)
    verifier = LicenseVerifier(data_dir=user_data_dir)

    app = QApplication(sys.argv)

    # 主题模式提前读取（与 MainWindow 内 AppState 同源），splash 不闪变
    try:
        theme_mode = AppState(data_manager, data_manager.load_progress()).get_theme_mode()
    except Exception as e:  # noqa: BLE001 - 主题读取失败不阻断启动，回退浅色
        logger.warning("启动时读取主题模式失败，回退 light: %s", e)
        theme_mode = "light"

    splash = _build_splash(app, theme_mode)
    splash.show()
    app.processEvents()

    # 后台线程加载 license + 题库
    result_queue: "queue.Queue[LoadSuccess | LoadFailure]" = queue.Queue()
    thread = threading.Thread(
        target=_load_app_data_async,
        args=(data_manager, verifier, result_queue),
        daemon=True,  # 主进程退出时自动结束
        name="app-data-loader",
    )
    thread.start()

    def check_loading() -> None:
        """主线程轮询 queue，加载完成后切换到 MainWindow。"""
        try:
            result = result_queue.get_nowait()
        except queue.Empty:
            return  # 定时器持续运行（L1：定时器随 splash 销毁释放）

        if isinstance(result, LoadFailure):
            log_error(logger, "题库数据加载失败", mode=result.mode)
            splash.close()
            QMessageBox.critical(None, "错误", f"题库数据加载失败:\n\n{result.message}")
            sys.exit(1)

        if not result.questions:
            splash.close()
            QMessageBox.critical(None, "错误", "未能解析出任何题目！")
            sys.exit(1)

        splash.close()
        try:
            window = MainWindow(
                result.questions,
                data_manager,
                license_status=result.status,
                meta=result.meta,
                license_dir=user_data_dir,
            )
            window.show()
            # license.dat 有文件但验证失败时告警用户
            if result.license_failed:
                QTimer.singleShot(
                    300,
                    lambda: QMessageBox.warning(
                        window,
                        "授权提示",
                        "本地注册码验证失败，已降级试用模式。\n请重新输入注册码。",
                    ),
                )
        except Exception as e:  # noqa: BLE001 - 启动失败必须留痕并向用户呈现（L1 静默失败红线）
            log_error(
                logger,
                "程序启动失败",
                exc=e,
                status=result.status.value if result.status else None,
            )
            QMessageBox.critical(None, "启动错误", f"程序启动失败:\n\n{e}")
            sys.exit(1)

    poll_timer = QTimer(splash)
    poll_timer.setInterval(100)
    poll_timer.timeout.connect(check_loading)
    poll_timer.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
