"""main_window.py 模块级纯逻辑单元测试（TD-11 拆分配套）。

仅测试从 _show_license_dialog 抽取出的纯逻辑函数：
  - _get_license_error_message: 错误码 → 用户可读消息
  - _verify_and_save_license: 验证注册码 + 持久化

UI 构建部分（tk.Toplevel/Label/Text 等）不在此测试范围。
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ui.main_window import (  # pylint: disable=wrong-import-position
    _get_license_error_message,
    _verify_and_save_license,
    _LICENSE_ERROR_MESSAGES,
)
from license import LicenseStatus, LicenseError  # pylint: disable=wrong-import-position


# ---------- _get_license_error_message 测试 ----------

def test_error_message_none():
    """err=None 时返回默认失败消息。"""
    assert _get_license_error_message(None) == "授权失败，请检查注册码。"


def test_error_message_invalid_signature():
    """INVALID_SIGNATURE 错误。"""
    assert _get_license_error_message(LicenseError.INVALID_SIGNATURE) == "注册码无效，请联系作者。"


def test_error_message_wrong_machine():
    """WRONG_MACHINE 错误。"""
    assert _get_license_error_message(LicenseError.WRONG_MACHINE) == "注册码不属于本机，请确认机器码后重新申请。"


def test_error_message_corrupt_questions():
    """CORRUPT_QUESTIONS 错误。"""
    assert _get_license_error_message(LicenseError.CORRUPT_QUESTIONS) == "题库密文损坏，请联系作者。"


def test_error_message_corrupt_license():
    """CORRUPT_LICENSE_FILE 错误。"""
    assert _get_license_error_message(LicenseError.CORRUPT_LICENSE_FILE) == "注册码文件损坏。"


def test_error_message_unknown():
    """未知错误码返回兜底消息。"""
    fake_err = MagicMock()
    fake_err.value = 'unknown_error'
    assert _get_license_error_message(fake_err) == "授权失败。"


def test_error_message_dict_keys_complete():
    """错误消息字典应覆盖所有 LicenseError 枚举值 + None。"""
    expected_keys = {None} | {e.value for e in LicenseError}
    assert set(_LICENSE_ERROR_MESSAGES.keys()) == expected_keys


# ---------- _verify_and_save_license 测试 ----------

def test_verify_and_save_success():
    """验证成功且保存成功 → (True, 成功消息, True)。"""
    with patch('ui.main_window.verify', return_value=(LicenseStatus.AUTHORIZED, 'K123', None)):
        mock_verifier = MagicMock()
        mock_verifier.save_license.return_value = True
        with patch('ui.main_window.LicenseVerifier', return_value=mock_verifier):
            success, msg, should_close = _verify_and_save_license('valid-code', '/tmp/data')
    assert success is True
    assert "授权成功" in msg
    assert should_close is True
    mock_verifier.save_license.assert_called_once_with('valid-code')


def test_verify_and_save_save_fails():
    """验证成功但保存失败 → (False, 失败消息, False)。"""
    with patch('ui.main_window.verify', return_value=(LicenseStatus.AUTHORIZED, 'K123', None)):
        mock_verifier = MagicMock()
        mock_verifier.save_license.return_value = False
        with patch('ui.main_window.LicenseVerifier', return_value=mock_verifier):
            success, msg, should_close = _verify_and_save_license('valid-code', '/tmp/data')
    assert success is False
    assert "保存到本地失败" in msg
    assert should_close is False


def test_verify_and_save_invalid_code():
    """验证失败（无效签名）→ (False, 错误消息, False)。"""
    with patch('ui.main_window.verify',
               return_value=(LicenseStatus.TRIAL, None, LicenseError.INVALID_SIGNATURE)):
        success, msg, should_close = _verify_and_save_license('bad-code', '/tmp/data')
    assert success is False
    assert "注册码无效" in msg
    assert should_close is False


def test_verify_and_save_wrong_machine():
    """验证失败（机器码不匹配）→ (False, 错误消息, False)。"""
    with patch('ui.main_window.verify',
               return_value=(LicenseStatus.TRIAL, None, LicenseError.WRONG_MACHINE)):
        success, msg, should_close = _verify_and_save_license('code', '/tmp/data')
    assert success is False
    assert "不属于本机" in msg
    assert should_close is False


def test_verify_and_save_no_key_authorized():
    """验证状态 AUTHORIZED 但 k 为 None → 视为失败。"""
    with patch('ui.main_window.verify', return_value=(LicenseStatus.AUTHORIZED, None, None)):
        success, msg, should_close = _verify_and_save_license('code', '/tmp/data')
    assert success is False
    assert should_close is False
