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
import tempfile
import threading
from dataclasses import dataclass
from typing import Any, cast

from PySide6.QtCore import Qt, QSharedMemory, QTimer
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
    else:
        user_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    # 两种模式都确保目录存在：开发模式漏创建时，日志/进度写在缺失目录上会在
    # 任何友好提示之前裸崩（RotatingFileHandler FileNotFoundError）
    os.makedirs(user_data_dir, exist_ok=True)
    return user_data_dir


def _setup_logging(user_data_dir: str) -> None:
    """配置 logging 到 user_data_dir/app.log，启用轮转避免日志无限增长。

    目录不可写（只读位置/权限）时回退系统临时目录，再不行退 NullHandler：
    日志配置失败不得阻断启动，且每次降级都留痕（stderr），不静默。
    """
    try:
        configure_app_logging(os.path.join(user_data_dir, "app.log"), level=logging.WARNING)
        return
    except OSError as e:
        print(f"日志目录不可用（{e}），回退系统临时目录", file=sys.stderr)
    fallback_file = os.path.join(tempfile.gettempdir(), "acp-cc-practice.log")
    try:
        configure_app_logging(fallback_file, level=logging.WARNING)
    except OSError as e:
        print(f"临时目录日志同样不可用（{e}），本次运行无文件日志", file=sys.stderr)
        logging.getLogger().addHandler(logging.NullHandler())


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


# 单实例保护（产品决策 2026-10-19：不允许多开——双开会整文件覆写 progress.json，
# 后写者赢导致一端进度静默丢失）。Windows 上共享内存段随进程退出自动释放，
# 崩溃无残留；非 Windows 平台段可能残留，但授权机制本就仅支持 Windows。
_SINGLE_INSTANCE_KEY = "acp-cc-single-v1"  # 段名 ≤32 字符：高熵密钥扫描按长度区分字面量语义
_guard: QSharedMemory | None = None  # 进程生命周期内持有引用，防止段提前释放


def _acquire_single_instance() -> bool:
    """尝试占用单实例共享内存段；已被其它实例占用返回 False。"""
    global _guard
    guard = QSharedMemory(_SINGLE_INSTANCE_KEY)
    if guard.create(1):  # 成功即同时 attach，段随本进程存活
        _guard = guard
        return True
    if guard.error() == QSharedMemory.SharedMemoryError.AlreadyExists:
        return False
    # 非占用类错误（权限等）：留痕后放行——双开保护降级为尽力而为，
    # 不因 shm 异常把应用变成完全无法启动（fail-open，风险上限=旧行为）
    logging.getLogger(__name__).warning(
        "单实例共享内存创建失败: %s（双开保护本次失效）", guard.errorString()
    )
    return False


def main() -> None:
    base_dir = _resolve_base_dir()
    user_data_dir = _resolve_user_data_dir()
    _setup_logging(user_data_dir)
    logger = logging.getLogger(__name__)

    data_manager = DataManager(base_dir, user_data_dir=user_data_dir)
    verifier = LicenseVerifier(data_dir=user_data_dir)

    app = QApplication(sys.argv)

    if not _acquire_single_instance():
        QMessageBox.warning(None, "提示", "程序已在运行，请勿重复打开。")
        sys.exit(0)

    # 进度只解析一次（原先此处取主题、MainWindow 构造各解析一遍，损坏处理
    # 要在两处保持一致）；权限类读取失败在此显式呈现（与原启动兜底同语义）
    try:
        progress = data_manager.load_progress()
    except DataLoadError as e:
        log_error(logger, "无法读取进度文件", exc=e, progress_file=data_manager.progress_file)
        QMessageBox.critical(None, "错误", f"无法读取进度文件:\n\n{e}")
        sys.exit(1)
    theme_mode = AppState(data_manager, progress).get_theme_mode()

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
        # 结果已到手：close() 不销毁控件，QTimer(splash) 随 QObject 树继续存活，
        # 不显式停止则 100ms 轮询在整个应用生命周期空转
        poll_timer.stop()

        if isinstance(result, LoadFailure):
            log_error(logger, "题库数据加载失败", mode=result.mode)
            splash.close()
            QMessageBox.critical(None, "错误", f"题库数据加载失败:\n\n{result.message}")
            # app.exit(1) 而非 sys.exit(1)：SystemExit 从 C++ 事件循环抛出会
            # 打印 traceback 并绕过正常清理；退出码经 app.exec() 返回值带出。
            # 显式 return：app.exit 无 NoReturn 类型，靠 return 收敛控制流
            app.exit(1)
            return

        if not result.questions:
            splash.close()
            QMessageBox.critical(None, "错误", "未能解析出任何题目！")
            app.exit(1)
            return

        splash.close()
        try:
            window = MainWindow(
                result.questions,
                data_manager,
                license_status=result.status,
                meta=result.meta,
                license_dir=user_data_dir,
                progress=progress,
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
            app.exit(1)
            return

    poll_timer = QTimer(splash)
    poll_timer.setInterval(100)
    poll_timer.timeout.connect(check_loading)
    poll_timer.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
