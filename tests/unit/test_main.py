"""main.py 单元测试。

覆盖范围：
- 日志配置使用 RotatingFileHandler 防止 app.log 无限增长
"""
import sys
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from main import _setup_logging  # pylint: disable=wrong-import-position


def test_setup_logging_uses_rotating_file_handler(tmp_path):
    """_setup_logging 应使用 RotatingFileHandler 并限制单文件大小与备份数。"""
    log_dir = tmp_path / 'logs'
    log_dir.mkdir()

    with patch('logging.basicConfig') as mock_basic_config:
        _setup_logging(str(log_dir))

    mock_basic_config.assert_called_once()
    call_kwargs = mock_basic_config.call_args.kwargs
    handlers = call_kwargs['handlers']
    assert len(handlers) == 1

    handler = handlers[0]
    assert isinstance(handler, logging.handlers.RotatingFileHandler)
    assert handler.maxBytes == 5 * 1024 * 1024
    assert handler.backupCount == 3
    assert handler.encoding == 'utf-8'


def test_setup_logging_creates_handler_with_correct_path(tmp_path):
    """RotatingFileHandler 应指向 user_data_dir/app.log。"""
    log_dir = tmp_path / 'logs'
    log_dir.mkdir()
    expected_log = str(log_dir / 'app.log')

    with patch('logging.basicConfig') as mock_basic_config:
        _setup_logging(str(log_dir))

    handler = mock_basic_config.call_args.kwargs['handlers'][0]
    assert handler.baseFilename == expected_log
