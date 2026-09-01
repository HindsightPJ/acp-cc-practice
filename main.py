import sys
import os
import logging
import tkinter as tk
import ttkbootstrap as ttkb
import threading
import queue
from dataclasses import dataclass
from tkinter import messagebox

from typing import Any, cast

from data_manager import DataManager, DataLoadError
from license import LicenseStatus
from license.verifier import LicenseVerifier
from logging_utils import configure_app_logging, log_error
from models import Question
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


@dataclass
class LoadSuccess:
    """后台线程加载成功的结果。"""

    status: LicenseStatus
    key: str | None
    license_failed: bool
    questions: list[Question]
    meta: dict[str, Any] | None


@dataclass
class LoadFailure:
    """后台线程加载失败的结果。"""

    message: str
    mode: str = "unknown"


def _reset_ttkbootstrap_style() -> None:
    """重置 ttkbootstrap 进程级 Style 单例，使其绑定下一个新建的 root。

    splash 销毁后单例仍指向已销毁解释器；不重置的话，MainWindow 应用
    journal 主题时会在死解释器上触发 ttk::ThemeChanged 后台报错（stderr
    噪音）。同时清理 Publisher 残留订阅：ttkbootstrap 1.10.1 注册的控件
    主题回调不随控件销毁注销。
    """
    ttkb.style.Style.instance = None
    ttkb.publisher.Publisher.clear_subscribers()


def _show_splash(root: tk.Tk) -> None:
    """在 root 上显示加载中界面。"""
    from ui.theme import theme, font_ui_semibold

    root.configure(bg=theme.BG_PAGE)
    label = tk.Label(
        root,
        text="正在加载题库...",
        font=font_ui_semibold(13),
        fg=theme.TEXT_PRIMARY,
        bg=theme.BG_PAGE,
    )
    label.pack(expand=True)


def _load_app_data_async(
    data_manager: DataManager,
    verifier: LicenseVerifier,
    result_queue: "queue.Queue[LoadSuccess | LoadFailure]",
) -> None:
    """后台线程：执行 license 验证 + 题库加载，结果放入 queue。

    P0-1: 将 PowerShell 子进程（0.2~5s）+ PBKDF2 60 万次迭代（0.3~1s）
    + Fernet 解密（50~300ms）从主线程移到后台线程，UI 立即显示 splash。
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
        result_queue.put(LoadSuccess(status, key, license_failed, questions, meta))
    except Exception as e:  # pylint: disable=broad-except
        # 兜底：任何未预期异常都通过 queue 传回主线程，避免线程静默退出
        result_queue.put(LoadFailure(f"加载失败: {e}", "unknown"))


def main() -> None:
    base_dir = _resolve_base_dir()
    user_data_dir = _resolve_user_data_dir()
    _setup_logging(user_data_dir)
    logger = logging.getLogger(__name__)

    data_manager = DataManager(base_dir, user_data_dir=user_data_dir)
    verifier = LicenseVerifier(data_dir=user_data_dir)

    # P0-1: 先显示 splash 窗口，避免 PowerShell + PBKDF2 阻塞 UI 0.5~6 秒
    # [VERSION_LOCKED] ttkbootstrap 1.10.1：splash 与主窗口统一 journal 主题
    splash = ttkb.Window(themename="journal")
    splash.title("ACP 云计算练习")
    splash.geometry("320x160")
    # 居中显示（基于屏幕尺寸）
    splash.update_idletasks()
    screen_w = splash.winfo_screenwidth()
    screen_h = splash.winfo_screenheight()
    x = (screen_w - 320) // 2
    y = (screen_h - 160) // 2
    splash.geometry(f"320x160+{x}+{y}")
    splash.overrideredirect(False)  # 保留标题栏，让用户能拖动/关闭

    _show_splash(splash)

    # 启动后台线程加载 license + 题库
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
            splash.after(100, check_loading)
            return

        # 销毁 splash（必须先 withdraw 再 destroy，避免闪烁）
        splash.withdraw()

        if isinstance(result, LoadFailure):
            log_error(logger, "题库数据加载失败", mode=result.mode)
            splash.destroy()
            _show_fatal_error("错误", f"题库数据加载失败:\n\n{result.message}")
            return

        splash.destroy()

        if not result.questions:
            _show_fatal_error("错误", "未能解析出任何题目！")
            return

        try:
            # splash（第一个 root）已销毁：重置 Style 单例后 MainWindow 的
            # journal 主题才能正确应用到新解释器
            _reset_ttkbootstrap_style()
            app = MainWindow(
                result.questions,
                data_manager,
                license_status=result.status,
                meta=result.meta,
                license_dir=user_data_dir,
            )
            # license.dat 有文件但验证失败时告警用户
            if result.license_failed:
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
            log_error(
                logger,
                "程序启动失败",
                exc=e,
                status=result.status.value if result.status else None,
            )
            _show_fatal_error("启动错误", f"程序启动失败:\n\n{str(e)}")

    splash.after(100, check_loading)
    splash.mainloop()


if __name__ == "__main__":
    main()
