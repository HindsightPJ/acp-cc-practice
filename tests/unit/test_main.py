"""main.py 单元测试。

覆盖范围：
- 日志配置使用 RotatingFileHandler 防止 app.log 无限增长
- TD-31: 日志配置委托给 logging_utils.configure_app_logging
- 目录解析与后台数据加载
- M5: 日志目录不可写时回退系统临时目录 / NullHandler（不得阻断启动）
- M5: 开发模式同样确保 data 目录存在
"""

import logging
import logging.handlers
import os
import queue
import sys
import tempfile
from unittest.mock import MagicMock, patch

from data_manager import DataLoadError
from license import LicenseStatus
import main as main_module
from main import (
    LoadFailure,
    LoadSuccess,
    _load_app_data_async,
    _resolve_base_dir,
    _resolve_user_data_dir,
    _setup_logging,
)
from models import Question


MAIN_DIR = os.path.dirname(os.path.abspath(main_module.__file__))


def _get_rotating_handlers():
    return [
        h
        for h in logging.getLogger().handlers
        if isinstance(h, logging.handlers.RotatingFileHandler)
    ]


def test_setup_logging_uses_rotating_file_handler(tmp_path):
    """_setup_logging 应使用 RotatingFileHandler 并限制单文件大小与备份数。"""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    # 清理已有 RotatingFileHandler，避免历史状态干扰
    for h in _get_rotating_handlers():
        logging.getLogger().removeHandler(h)

    with patch("main.configure_app_logging") as mock_configure:
        _setup_logging(str(log_dir))

    mock_configure.assert_called_once()
    call_args = mock_configure.call_args
    assert call_args.args[0] == str(log_dir / "app.log")
    assert call_args.kwargs.get("level") == logging.WARNING


def test_setup_logging_creates_handler_with_correct_path(tmp_path):
    """RotatingFileHandler 应指向 user_data_dir/app.log。"""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    expected_log = str(log_dir / "app.log")

    # 清理已有 RotatingFileHandler
    for h in _get_rotating_handlers():
        logging.getLogger().removeHandler(h)

    _setup_logging(str(log_dir))

    handlers = _get_rotating_handlers()
    assert len(handlers) >= 1
    handler = handlers[-1]
    assert handler.baseFilename == expected_log
    assert handler.maxBytes == 5 * 1024 * 1024
    assert handler.backupCount == 3
    assert handler.encoding == "utf-8"


def _make_question(number=1):
    """构造一个最小 Question 实例。"""
    return Question(number=number, content=f"题目{number}")


def test_resolve_base_dir_returns_meipass_when_present(monkeypatch):
    """PyInstaller 打包后优先使用 sys._MEIPASS。"""
    monkeypatch.setattr(sys, "_MEIPASS", "/fake/meipass", raising=False)
    assert _resolve_base_dir() == "/fake/meipass"


def test_resolve_base_dir_returns_script_dir_without_meipass(monkeypatch):
    """未打包时返回脚本所在目录。"""
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    assert _resolve_base_dir() == MAIN_DIR


def test_resolve_user_data_dir_returns_exe_dir_data_when_frozen(monkeypatch):
    """打包后返回 exe 同级 data 目录。"""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", "/fake/app/myapp.exe", raising=False)
    with patch("main.os.makedirs"):
        result = _resolve_user_data_dir()
    assert result == os.path.join("/fake/app", "data")


def test_resolve_user_data_dir_returns_script_dir_data_when_not_frozen(monkeypatch):
    """开发模式返回脚本目录下的 data。"""
    monkeypatch.delattr(sys, "frozen", raising=False)
    result = _resolve_user_data_dir()
    assert result == os.path.join(MAIN_DIR, "data")


def test_resolve_user_data_dir_creates_dir_in_dev_mode(monkeypatch, tmp_path):
    """M5: 开发模式也必须确保 data 目录存在——此前只有打包分支 makedirs，
    漏创建时 RotatingFileHandler 会在任何友好提示之前裸崩。"""
    monkeypatch.delattr(sys, "frozen", raising=False)
    fake_main = tmp_path / "main.py"
    fake_main.write_text("# placeholder", encoding="utf-8")
    monkeypatch.setattr(main_module, "__file__", str(fake_main))

    result = _resolve_user_data_dir()

    assert result == str(tmp_path / "data")
    assert os.path.isdir(result)


def test_setup_logging_falls_back_to_tempdir_when_unwritable(tmp_path, monkeypatch):
    """M5: 日志目录不可写 → 回退系统临时目录，不阻断启动（留痕 stderr）。"""
    real_configure = main_module.configure_app_logging
    calls: list[str] = []

    def failing_then_temp(log_path, **kwargs):
        calls.append(log_path)
        if len(calls) == 1:
            raise PermissionError("read-only location")
        return real_configure(log_path, **kwargs)

    monkeypatch.setattr(main_module, "configure_app_logging", failing_then_temp)

    _setup_logging(str(tmp_path / "unwritable"))

    # 第一次（目标目录）失败，第二次（临时目录）成功
    assert len(calls) == 2
    assert calls[1] == os.path.join(tempfile.gettempdir(), "acp-cc-practice.log")


def test_setup_logging_null_handler_when_tempdir_also_fails(tmp_path, monkeypatch):
    """M5: 连临时目录都不可写 → NullHandler 兜底，仍不崩（最后手段）。"""
    monkeypatch.setattr(
        main_module, "configure_app_logging", MagicMock(side_effect=PermissionError("denied"))
    )

    _setup_logging(str(tmp_path / "unwritable"))

    assert any(isinstance(h, logging.NullHandler) for h in logging.getLogger().handlers)


# ---------- 单实例保护（M4 / 产品决策 2026-10-19：不允许多开） ----------


def test_single_instance_second_acquire_rejected(qapp, monkeypatch):
    """第二实例 create 失败（AlreadyExists）→ 返回 False，拒绝启动。"""
    monkeypatch.setattr(main_module, "_guard", None)
    assert main_module._acquire_single_instance() is True  # 第一实例占用
    assert main_module._acquire_single_instance() is False  # 第二实例被拒


# ---------- M15: check_loading 四分支（此前 main() 48% 覆盖的主盲区） ----------


class _FakeTimer:
    """QTimer 替身：捕获 timeout 回调与 singleShot 延迟任务。"""

    single_shots: list[tuple[int, object]] = []

    def __init__(self, parent=None) -> None:
        self.connected = None
        self.started = False
        self.stopped = False

    @staticmethod
    def singleShot(msec, callback) -> None:
        _FakeTimer.single_shots.append((msec, callback))

    class _Signal:
        def __init__(self, owner) -> None:
            self._owner = owner

        def connect(self, cb) -> None:
            self._owner.connected = cb

    @property
    def timeout(self):
        return _FakeTimer._Signal(self)

    def setInterval(self, msec) -> None:
        self.interval = msec

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


def _drive_main_capture(monkeypatch, result=None):
    """以 mock 装配驱动 main()，捕获 check_loading 回调与全部交互 mock。

    result=None 时队列保持为空（模拟"加载中"）；否则预填该结果——
    后台线程被 mock 掉不运行，结果视为已就绪。
    返回 (app_mock, exit_calls, msgbox, window_cls, timer)。
    """
    prefilled: "queue.Queue" = queue.Queue()
    if result is not None:
        prefilled.put(result)
    _FakeTimer.single_shots = []

    holder: dict = {}

    real_timer_init = _FakeTimer.__init__

    def recording_init(self, parent=None) -> None:
        real_timer_init(self, parent)
        holder["timer"] = self

    monkeypatch.setattr(_FakeTimer, "__init__", recording_init)

    app_mock = MagicMock()
    app_mock.exec.return_value = 0
    monkeypatch.setattr(main_module, "QApplication", MagicMock(return_value=app_mock))
    monkeypatch.setattr(main_module, "QTimer", _FakeTimer)
    msgbox = MagicMock()
    monkeypatch.setattr(main_module, "QMessageBox", msgbox)
    window_cls = MagicMock()
    monkeypatch.setattr(main_module, "MainWindow", window_cls)
    monkeypatch.setattr(main_module, "_build_splash", MagicMock(return_value=MagicMock()))
    monkeypatch.setattr(main_module, "_acquire_single_instance", MagicMock(return_value=True))
    monkeypatch.setattr(main_module, "DataManager", MagicMock())
    monkeypatch.setattr(main_module, "LicenseVerifier", MagicMock())
    monkeypatch.setattr(main_module, "AppState", MagicMock())
    monkeypatch.setattr(main_module.threading, "Thread", MagicMock())
    monkeypatch.setattr(main_module.queue, "Queue", MagicMock(return_value=prefilled))
    exit_calls: list[object] = []
    monkeypatch.setattr(sys, "exit", lambda code=0: exit_calls.append(code))

    main_module.main()
    return app_mock, exit_calls, msgbox, window_cls, holder["timer"]


def test_check_loading_failure_branch(qapp, monkeypatch):
    """LoadFailure → critical 弹窗 + timer 停止 + app.exit(1)，不走 MainWindow。"""
    app_mock, exit_calls, msgbox, window_cls, timer = _drive_main_capture(
        monkeypatch, LoadFailure("boom", "trial")
    )
    timer.connected()

    msgbox.critical.assert_called_once()
    assert timer.stopped is True
    app_mock.exit.assert_called_once_with(1)
    window_cls.assert_not_called()
    # main() 正常跑到 app.exec()（mock 返回 0）；退出码 1 走的是 app.exit 而非 sys.exit
    assert exit_calls == [0]


def test_check_loading_empty_questions_branch(qapp, monkeypatch):
    """成功但零题目 → critical + app.exit(1)。"""
    app_mock, exit_calls, msgbox, window_cls, timer = _drive_main_capture(
        monkeypatch, LoadSuccess(LicenseStatus.TRIAL, False, [], None)
    )
    timer.connected()

    msgbox.critical.assert_called_once()
    app_mock.exit.assert_called_once_with(1)
    window_cls.assert_not_called()


def test_check_loading_success_branch(qapp, monkeypatch):
    """正常成功 → MainWindow 构造 + show，无弹窗、无 exit。"""
    questions = [_make_question(1)]
    app_mock, exit_calls, msgbox, window_cls, timer = _drive_main_capture(
        monkeypatch, LoadSuccess(LicenseStatus.TRIAL, False, questions, {"total": 1})
    )
    timer.connected()

    window_cls.assert_called_once()
    window_cls.return_value.show.assert_called_once()
    msgbox.critical.assert_not_called()
    app_mock.exit.assert_not_called()


def test_check_loading_license_failed_warning(qapp, monkeypatch):
    """license.dat 验证失败降级 → 延迟 300ms 告警弹窗，主窗口照常启动。"""
    app_mock, exit_calls, msgbox, window_cls, timer = _drive_main_capture(
        monkeypatch, LoadSuccess(LicenseStatus.TRIAL, True, [_make_question(1)], None)
    )
    timer.connected()

    window_cls.assert_called_once()
    assert len(_FakeTimer.single_shots) == 1
    assert _FakeTimer.single_shots[0][0] == 300
    _FakeTimer.single_shots[0][1]()  # 触发延迟告警
    msgbox.warning.assert_called_once()


def test_check_loading_queue_empty_keeps_polling(qapp, monkeypatch):
    """队列空（加载中）→ 直接返回，无弹窗无退出，timer 保持运行。"""
    app_mock, exit_calls, msgbox, window_cls, timer = _drive_main_capture(monkeypatch)
    timer.connected()

    msgbox.critical.assert_not_called()
    app_mock.exit.assert_not_called()
    window_cls.assert_not_called()
    assert timer.started is True
    assert timer.stopped is False


def test_load_app_data_async_authorized_loads_full_questions():
    """已授权且有 key 时加载完整题库。"""
    dm = MagicMock()
    verifier = MagicMock()
    result_queue: "queue.Queue[LoadSuccess | LoadFailure]" = queue.Queue()

    full_questions = [_make_question(1)]
    meta = {"total": 100}
    verifier.check_local_license.return_value = (LicenseStatus.AUTHORIZED, "key123", False)
    dm.load_full_questions.return_value = full_questions
    dm.load_meta.return_value = meta

    _load_app_data_async(dm, verifier, result_queue)
    result = result_queue.get_nowait()

    assert isinstance(result, LoadSuccess)
    dm.load_full_questions.assert_called_once_with("key123")
    dm.load_trial_questions.assert_not_called()
    assert result.status == LicenseStatus.AUTHORIZED
    assert result.license_failed is False
    assert result.questions == full_questions
    assert result.meta == meta


def test_load_app_data_async_non_authorized_loads_trial_questions():
    """未授权时加载试用题库。"""
    dm = MagicMock()
    verifier = MagicMock()
    result_queue: "queue.Queue[LoadSuccess | LoadFailure]" = queue.Queue()

    trial_questions = [_make_question(2)]
    meta = {"total": 20}
    verifier.check_local_license.return_value = (LicenseStatus.TRIAL, None, True)
    dm.load_trial_questions.return_value = trial_questions
    dm.load_meta.return_value = meta

    _load_app_data_async(dm, verifier, result_queue)
    result = result_queue.get_nowait()

    assert isinstance(result, LoadSuccess)
    dm.load_trial_questions.assert_called_once()
    dm.load_full_questions.assert_not_called()
    assert result.status == LicenseStatus.TRIAL
    assert result.license_failed is True
    assert result.questions == trial_questions
    assert result.meta == meta


def test_load_app_data_async_data_load_error_trial_puts_load_failure():
    """试用题库加载失败时 queue 中放入 mode=trial 的 LoadFailure。"""
    dm = MagicMock()
    verifier = MagicMock()
    result_queue: "queue.Queue[LoadSuccess | LoadFailure]" = queue.Queue()

    verifier.check_local_license.return_value = (LicenseStatus.TRIAL, None, False)
    dm.load_trial_questions.side_effect = DataLoadError("trial data missing")

    _load_app_data_async(dm, verifier, result_queue)
    result = result_queue.get_nowait()

    assert isinstance(result, LoadFailure)
    assert "trial data missing" in result.message
    assert result.mode == "trial"


def test_load_app_data_async_data_load_error_authorized_puts_load_failure():
    """授权题库加载失败时 queue 中放入 mode=unknown 的 LoadFailure。"""
    dm = MagicMock()
    verifier = MagicMock()
    result_queue: "queue.Queue[LoadSuccess | LoadFailure]" = queue.Queue()

    verifier.check_local_license.return_value = (LicenseStatus.AUTHORIZED, "key123", False)
    dm.load_full_questions.side_effect = DataLoadError("full data missing")

    _load_app_data_async(dm, verifier, result_queue)
    result = result_queue.get_nowait()

    assert isinstance(result, LoadFailure)
    assert "full data missing" in result.message
    assert result.mode == "unknown"


def test_load_app_data_async_unexpected_exception_puts_load_failure():
    """未预期异常被捕获并放入 mode=unknown 的 LoadFailure。"""
    dm = MagicMock()
    verifier = MagicMock()
    result_queue: "queue.Queue[LoadSuccess | LoadFailure]" = queue.Queue()

    verifier.check_local_license.side_effect = RuntimeError("boom")

    _load_app_data_async(dm, verifier, result_queue)
    result = result_queue.get_nowait()

    assert isinstance(result, LoadFailure)
    assert "boom" in result.message
    assert result.mode == "unknown"
