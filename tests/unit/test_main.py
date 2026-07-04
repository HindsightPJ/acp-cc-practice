"""main.py 单元测试。

覆盖范围：
- 日志配置使用 RotatingFileHandler 防止 app.log 无限增长
- TD-31: 日志配置委托给 logging_utils.configure_app_logging
- 目录解析与后台数据加载
"""
import logging
import logging.handlers
import os
import queue
import sys
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
        h for h in logging.getLogger().handlers
        if isinstance(h, logging.handlers.RotatingFileHandler)
    ]


def test_setup_logging_uses_rotating_file_handler(tmp_path):
    """_setup_logging 应使用 RotatingFileHandler 并限制单文件大小与备份数。"""
    log_dir = tmp_path / 'logs'
    log_dir.mkdir()

    # 清理已有 RotatingFileHandler，避免历史状态干扰
    for h in _get_rotating_handlers():
        logging.getLogger().removeHandler(h)

    with patch('main.configure_app_logging') as mock_configure:
        _setup_logging(str(log_dir))

    mock_configure.assert_called_once()
    call_args = mock_configure.call_args
    assert call_args.args[0] == str(log_dir / 'app.log')
    assert call_args.kwargs.get('level') == logging.WARNING


def test_setup_logging_creates_handler_with_correct_path(tmp_path):
    """RotatingFileHandler 应指向 user_data_dir/app.log。"""
    log_dir = tmp_path / 'logs'
    log_dir.mkdir()
    expected_log = str(log_dir / 'app.log')

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
    assert handler.encoding == 'utf-8'


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
    assert result.key == "key123"
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
    assert result.key is None
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
