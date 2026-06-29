"""fingerprint.py 单元测试。"""
import sys
import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from license.fingerprint import (  # pylint: disable=wrong-import-position
    get_machine_guid,
    compute_machine_code,
    get_machine_code_or_none,
    UnsupportedOSError,
)


def test_get_machine_guid_on_windows(monkeypatch):
    """Windows 下应通过注册表读取 MachineGuid。"""
    monkeypatch.setattr('sys.platform', 'win32')
    monkeypatch.setattr('winreg.HKEY_LOCAL_MACHINE', 0)
    fake_key = object()
    with patch('winreg.OpenKey', return_value=fake_key):
        with patch('winreg.QueryValueEx', return_value=('test-guid-123', 1)):
            with patch('winreg.CloseKey'):
                guid = get_machine_guid()
    assert guid == 'test-guid-123'


def test_get_machine_guid_non_windows(monkeypatch):
    """非 Windows 应抛 UnsupportedOSError。"""
    monkeypatch.setattr('sys.platform', 'linux')
    with pytest.raises(UnsupportedOSError):
        get_machine_guid()


def test_compute_machine_code_is_sha256_hex():
    """machine_code 应是 64 字符小写 hex，且与已知 SHA-256 向量一致。"""
    code = compute_machine_code('test-guid-123', 'A1B2C3D4', 'MYPC')
    assert len(code) == 64
    assert all(c in '0123456789abcdef' for c in code)
    # 已知向量：SHA-256('abc|XXX|YYY')
    expected = hashlib.sha256('abc|XXX|YYY'.encode('utf-8')).hexdigest()
    assert compute_machine_code('abc', 'XXX', 'YYY') == expected


def test_compute_machine_code_deterministic():
    """相同三维度应产生相同 machine_code，任一维度变化则不同。"""
    assert compute_machine_code('abc', 'XXX', 'YYY') == compute_machine_code('abc', 'XXX', 'YYY')
    # 任一维度变化 → 机器码不同
    assert compute_machine_code('abc', 'XXX', 'YYY') != compute_machine_code('abd', 'XXX', 'YYY')
    assert compute_machine_code('abc', 'XXX', 'YYY') != compute_machine_code('abc', 'XXY', 'YYY')
    assert compute_machine_code('abc', 'XXX', 'YYY') != compute_machine_code('abc', 'XXX', 'YYZ')


def test_get_machine_code_or_none_normal(monkeypatch):
    """Windows 正常路径应返回 64 字符机器码（三维度组合）。"""
    monkeypatch.setattr('sys.platform', 'win32')
    fake_key = object()
    with patch('winreg.OpenKey', return_value=fake_key):
        with patch('winreg.QueryValueEx', return_value=('test-guid-123', 1)):
            with patch('winreg.CloseKey'):
                with patch('license.fingerprint.get_volume_serial', return_value='A1B2C3D4'):
                    with patch('license.fingerprint.get_computer_name', return_value='MYPC'):
                        code = get_machine_code_or_none()
    assert code is not None
    assert len(code) == 64
    assert code == compute_machine_code('test-guid-123', 'A1B2C3D4', 'MYPC')


def test_get_machine_code_or_none_non_windows(monkeypatch):
    """非 Windows 应降级返回 None。"""
    monkeypatch.setattr('sys.platform', 'linux')
    assert get_machine_code_or_none() is None


def test_get_machine_code_or_none_registry_error(monkeypatch):
    """注册表读取失败应降级返回 None。"""
    monkeypatch.setattr('sys.platform', 'win32')
    with patch('winreg.OpenKey', side_effect=OSError('access denied')):
        assert get_machine_code_or_none() is None


def test_get_machine_code_or_none_volume_error(monkeypatch):
    """卷序列号读取失败应降级返回 None。"""
    monkeypatch.setattr('sys.platform', 'win32')
    fake_key = object()
    with patch('winreg.OpenKey', return_value=fake_key):
        with patch('winreg.QueryValueEx', return_value=('test-guid-123', 1)):
            with patch('winreg.CloseKey'):
                with patch('license.fingerprint.get_volume_serial',
                           side_effect=OSError('vol failed')):
                    assert get_machine_code_or_none() is None
