import sys
import os
import logging
import tkinter as tk
from tkinter import messagebox

from typing import cast

from data_manager import DataManager, DataLoadError
from license import LicenseStatus
from license.verifier import LicenseVerifier
from telemetry import configure_app_logging, log_error
from ui.main_window import MainWindow


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


def _show_fatal_error(title: str, message: str) -> None:
    """显示错误对话框后退出程序（TD-04 修复：消除 main() 中 4 处重复模式）。

    在 main() 的多处错误路径上使用，集中创建 tk.Tk + messagebox + sys.exit(1)。
    调用方自行决定是否在调用前记录日志（logger.error / logger.exception）。
    """
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(title, message)
    sys.exit(1)


def main():
    base_dir = _resolve_base_dir()
    user_data_dir = _resolve_user_data_dir()
    _setup_logging(user_data_dir)
    logger = logging.getLogger(__name__)

    data_manager = DataManager(base_dir, user_data_dir=user_data_dir)

    # 1. 检查本地授权（license.dat 写到 user_data_dir）
    verifier = LicenseVerifier(data_dir=user_data_dir)
    status, key, license_failed = verifier.check_local_license()

    # 2. 根据授权状态加载题库
    try:
        if status == LicenseStatus.AUTHORIZED and key:
            questions = data_manager.load_full_questions(key)
        else:
            # 试用模式：加载 trial，缺失则报错
            # P3-1: 收窄异常捕获——load_trial_questions 只会抛 DataLoadError
            # (OSError 已被它内部捕获并转抛 DataLoadError)，其他异常应上抛
            try:
                questions = data_manager.load_trial_questions()
            except DataLoadError as e:
                log_error(logger, "加载试用题库失败", exc=e, mode="trial")
                _show_fatal_error("错误", "试用题库缺失，请重新下载程序。")
    except DataLoadError as e:
        log_error(logger, "题库数据加载失败", exc=e, mode="unknown")
        _show_fatal_error("错误", f"题库数据加载失败:\n\n{str(e)}")

    if not questions:
        _show_fatal_error("错误", "未能解析出任何题目！")

    # 3. 加载元数据（用于 UI 显示总量）
    meta = data_manager.load_meta()

    try:
        app = MainWindow(
            questions, data_manager, license_status=status, meta=meta, license_dir=user_data_dir
        )
        # license.dat 有文件但验证失败时告警用户
        if license_failed:
            app.after(
                300,
                lambda: messagebox.showwarning(
                    "授权提示",
                    "本地注册码验证失败，已降级试用模式。\n请重新输入注册码。",
                    parent=app,
                ),
            )
        app.mainloop()
    except (tk.TclError, OSError, ValueError, KeyError, RuntimeError) as e:
        # P3-1: 收窄异常捕获——
        # tk.TclError: Tk/Tcl 内部错误（display 不可用、字体加载失败等）
        # OSError: 文件读写失败（progress.json / license.dat）
        # ValueError/KeyError: 配置或数据格式错误
        # RuntimeError: 其他运行时错误
        # 其他异常应上抛，便于开发者定位
        log_error(logger, "程序启动失败", exc=e, status=status.value if status else None)
        _show_fatal_error("启动错误", f"程序启动失败:\n\n{str(e)}")


if __name__ == "__main__":
    main()
