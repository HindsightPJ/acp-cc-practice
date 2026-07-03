"""main.py 单元测试。

覆盖范围：
- 日志配置使用 RotatingFileHandler 防止 app.log 无限增长
- TD-31: 日志配置委托给 logging_utils.configure_app_logging
"""
import logging
import logging.handlers
from unittest.mock import patch

import pytest

from main import _setup_logging


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
