"""fingerprint.py 单元测试。"""

import hashlib
import sys
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest

from license.fingerprint import (
    get_machine_guid,
    get_volume_serial,
    compute_machine_code,
    get_machine_code_or_none,
    get_bios_serial,
    UnsupportedOSError,
)


@pytest.mark.skipif(sys.platform != "win32", reason="winreg is Windows-only")
def test_get_machine_guid_on_windows(monkeypatch):
    """Windows 下应通过注册表读取 MachineGuid。"""
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setattr("winreg.HKEY_LOCAL_MACHINE", 0)
    fake_key = object()
    with patch("winreg.OpenKey", return_value=fake_key):
        with patch("winreg.QueryValueEx", return_value=("test-guid-123", 1)):
            with patch("winreg.CloseKey"):
                guid = get_machine_guid()
    assert guid == "test-guid-123"


def test_get_machine_guid_non_windows(monkeypatch):
    """非 Windows 应抛 UnsupportedOSError。"""
    monkeypatch.setattr("sys.platform", "linux")
    with pytest.raises(UnsupportedOSError):
        get_machine_guid()


# ---------- M18: get_volume_serial ctypes 链路（此前全 mock 跳过、CI 结构性失明） ----------


class _FakeUInt32:
    def __init__(self, v: int = 0) -> None:
        self.value = v


def _fake_ctypes(success: bool, serial: int = 0xA1B2C3D4):
    """跨平台 ctypes 替身：GetVolumeInformationW 按入参决定成败。

    fingerprint 自 2026-10-19 起模块级导入 ctypes，测试可整体替换该属性，
    使 Windows 专属链路在 ubuntu CI 上真实执行（替代结构性跳过）。
    """

    def fake_get_volume_info(drive, a, b, vol_ref, c, d, e, f):
        if success:
            vol_ref.value = serial
            return 1
        return 0

    return SimpleNamespace(
        c_uint32=_FakeUInt32,
        c_wchar_p=lambda s: s,
        create_unicode_buffer=lambda n: "",
        windll=SimpleNamespace(
            kernel32=SimpleNamespace(GetVolumeInformationW=fake_get_volume_info)
        ),
        byref=lambda x: x,
    )


def test_get_volume_serial_success(monkeypatch):
    """ctypes 调用链真实执行（桩替换模块属性）：成功读出 8 字符大写 hex。"""
    from license import fingerprint

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(fingerprint, "ctypes", _fake_ctypes(success=True))
    assert get_volume_serial() == "A1B2C3D4"


def test_get_volume_serial_api_failure_raises_oserror(monkeypatch):
    """GetVolumeInformationW 返回 0 → OSError（此前零覆盖的失败路径）。"""
    from license import fingerprint

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(fingerprint, "ctypes", _fake_ctypes(success=False))
    with pytest.raises(OSError):
        get_volume_serial()


def test_get_volume_serial_still_guards_non_windows(monkeypatch):
    """平台守卫先于 ctypes 调用：非 win32 仍抛 UnsupportedOSError。"""
    monkeypatch.setattr(sys, "platform", "linux")
    with pytest.raises(UnsupportedOSError):
        get_volume_serial()


def test_compute_machine_code_is_sha256_hex():
    """machine_code 应是 64 字符小写 hex，且与已知 SHA-256 向量一致。"""
    code = compute_machine_code("test-guid-123", "A1B2C3D4", "MYPC")
    assert len(code) == 64
    assert all(c in "0123456789abcdef" for c in code)
    # 已知向量：SHA-256('abc|XXX|YYY|')（TD-07: 第 4 维度 bios 默认空字符串）
    expected = hashlib.sha256("abc|XXX|YYY|".encode("utf-8")).hexdigest()
    assert compute_machine_code("abc", "XXX", "YYY") == expected


def test_compute_machine_code_deterministic():
    """相同四维度应产生相同 machine_code，任一维度变化则不同。"""
    assert compute_machine_code("abc", "XXX", "YYY") == compute_machine_code("abc", "XXX", "YYY")
    # 任一维度变化 → 机器码不同
    assert compute_machine_code("abc", "XXX", "YYY") != compute_machine_code("abd", "XXX", "YYY")
    assert compute_machine_code("abc", "XXX", "YYY") != compute_machine_code("abc", "XXY", "YYY")
    assert compute_machine_code("abc", "XXX", "YYY") != compute_machine_code("abc", "XXX", "YYZ")
    # TD-07: BIOS 维度变化 → 机器码不同
    assert compute_machine_code("abc", "XXX", "YYY", "BIOS1") != compute_machine_code(
        "abc", "XXX", "YYY", "BIOS2"
    )
    assert compute_machine_code("abc", "XXX", "YYY", "BIOS1") != compute_machine_code(
        "abc", "XXX", "YYY"
    )


@pytest.mark.skipif(sys.platform != "win32", reason="winreg is Windows-only")
def test_get_machine_code_or_none_normal(monkeypatch):
    """Windows 正常路径应返回 64 字符机器码（四维度组合）。"""
    monkeypatch.setattr("sys.platform", "win32")
    fake_key = object()
    with patch("winreg.OpenKey", return_value=fake_key):
        with patch("winreg.QueryValueEx", return_value=("test-guid-123", 1)):
            with patch("winreg.CloseKey"):
                with patch("license.fingerprint.get_volume_serial", return_value="A1B2C3D4"):
                    with patch("license.fingerprint.get_computer_name", return_value="MYPC"):
                        with patch("license.fingerprint.get_bios_serial", return_value="BIOS123"):
                            code = get_machine_code_or_none()
    assert code is not None
    assert len(code) == 64
    assert code == compute_machine_code("test-guid-123", "A1B2C3D4", "MYPC", "BIOS123")


# ---------- get_bios_serial 测试（TD-07）----------


def test_get_bios_serial_non_windows(monkeypatch):
    """非 Windows 平台应返回空字符串。"""
    monkeypatch.setattr("sys.platform", "linux")
    assert get_bios_serial() == ""


def test_get_bios_serial_powershell_success(monkeypatch):
    """PowerShell CIM 成功时应返回清理后的序列号。"""
    monkeypatch.setattr("sys.platform", "win32")
    fake_result = MagicMock(stdout="ABC-123\n\r\n", returncode=0)
    with patch("subprocess.run", return_value=fake_result):
        assert get_bios_serial() == "ABC-123"


def test_get_bios_serial_powershell_failure(monkeypatch):
    """PowerShell 调用失败时应返回空字符串。"""
    monkeypatch.setattr("sys.platform", "win32")
    with patch("subprocess.run", side_effect=OSError("powershell not found")):
        assert get_bios_serial() == ""


def test_get_bios_serial_timeout(monkeypatch):
    """PowerShell 超时应返回空字符串。"""
    import subprocess as _sp

    monkeypatch.setattr("sys.platform", "win32")
    with patch("subprocess.run", side_effect=_sp.TimeoutExpired(cmd="powershell", timeout=5)):
        assert get_bios_serial() == ""


def test_get_bios_serial_filters_placeholder(monkeypatch):
    """OEM 占位符值应被过滤为空字符串。"""
    monkeypatch.setattr("sys.platform", "win32")
    fake_result = MagicMock(stdout="Default string\n", returncode=0)
    with patch("subprocess.run", return_value=fake_result):
        assert get_bios_serial() == ""


def test_get_bios_serial_empty_output(monkeypatch):
    """PowerShell 输出为空时应返回空字符串。"""
    monkeypatch.setattr("sys.platform", "win32")
    fake_result = MagicMock(stdout="", returncode=0)
    with patch("subprocess.run", return_value=fake_result):
        assert get_bios_serial() == ""


def test_get_bios_serial_whitespace_output(monkeypatch):
    """PowerShell 输出仅含空白时应返回空字符串。"""
    monkeypatch.setattr("sys.platform", "win32")
    fake_result = MagicMock(stdout="\r\n  \n", returncode=0)
    with patch("subprocess.run", return_value=fake_result):
        assert get_bios_serial() == ""


def test_get_machine_code_or_none_non_windows(monkeypatch):
    """非 Windows 应降级返回 None。"""
    monkeypatch.setattr("sys.platform", "linux")
    assert get_machine_code_or_none() is None


@pytest.mark.skipif(sys.platform != "win32", reason="winreg is Windows-only")
def test_get_machine_code_or_none_registry_error(monkeypatch):
    """注册表读取失败应降级返回 None。"""
    monkeypatch.setattr("sys.platform", "win32")
    with patch("winreg.OpenKey", side_effect=OSError("access denied")):
        assert get_machine_code_or_none() is None


@pytest.mark.skipif(sys.platform != "win32", reason="winreg is Windows-only")
def test_get_machine_code_or_none_volume_error(monkeypatch):
    """卷序列号读取失败应降级返回 None。"""
    monkeypatch.setattr("sys.platform", "win32")
    fake_key = object()
    with patch("winreg.OpenKey", return_value=fake_key):
        with patch("winreg.QueryValueEx", return_value=("test-guid-123", 1)):
            with patch("winreg.CloseKey"):
                with patch(
                    "license.fingerprint.get_volume_serial", side_effect=OSError("vol failed")
                ):
                    assert get_machine_code_or_none() is None
