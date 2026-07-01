"""采集本机机器指纹。

平台：Windows
非 Windows：抛 UnsupportedOSError，由调用方降级为试用模式。

机器码 = SHA-256(MachineGuid + "|" + VolumeSerial(C:) + "|" + ComputerName + "|" + BiosSerial).hex()
四维度组合（TD-07: 新增 BIOS 序列号），单一维度克隆（如磁盘镜像）不足以绕过。
BIOS 序列号获取失败时用空字符串，其他三维度仍有效。
此值会显示给用户复制，并作为 PBKDF2 的 password 输入。
"""
import hashlib
import os
import socket
import subprocess
import sys
import logging
from typing import Optional, cast

logger = logging.getLogger(__name__)


class UnsupportedOSError(Exception):
    """当前平台不支持采集机器指纹。"""
    pass


def get_machine_guid() -> str:
    """读取 Windows MachineGuid。

    Returns:
        MachineGuid 字符串

    Raises:
        UnsupportedOSError: 非 Windows 平台
        OSError: 注册表读取失败
    """
    if sys.platform != 'win32':
        raise UnsupportedOSError(f"当前平台 {sys.platform} 不支持授权，仅支持 Windows")

    import winreg  # pylint: disable=import-outside-toplevel
    key = winreg.OpenKey(
        winreg.HKEY_LOCAL_MACHINE,
        r'SOFTWARE\Microsoft\Cryptography',
        0,
        winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
    )
    try:
        value, _ = winreg.QueryValueEx(key, 'MachineGuid')
        return cast(str, value)
    finally:
        winreg.CloseKey(key)


def get_volume_serial(drive: str = 'C:\\') -> str:
    """读取 Windows 磁盘卷序列号。

    Args:
        drive: 驱动器路径，默认 C:\\

    Returns:
        8 字符大写 hex 字符串（如 "A1B2C3D4"）

    Raises:
        UnsupportedOSError: 非 Windows 平台
        OSError: GetVolumeInformationW 调用失败
    """
    if sys.platform != 'win32':
        raise UnsupportedOSError(f"当前平台 {sys.platform} 不支持授权，仅支持 Windows")

    import ctypes  # pylint: disable=import-outside-toplevel
    volume_serial = ctypes.c_uint32(0)
    max_component = ctypes.c_uint32(0)
    fs_flags = ctypes.c_uint32(0)
    fs_name = ctypes.create_unicode_buffer(256)

    success = ctypes.windll.kernel32.GetVolumeInformationW(
        ctypes.c_wchar_p(drive),
        None, 0,
        ctypes.byref(volume_serial),
        ctypes.byref(max_component),
        ctypes.byref(fs_flags),
        fs_name, 256,
    )
    if not success:
        raise OSError(f"GetVolumeInformationW 失败，驱动器 {drive}")
    return f"{volume_serial.value:08X}"


def get_computer_name() -> str:
    """读取计算机名。

    直接使用 socket.gethostname() 获取，避免环境变量被伪造。
    返回值统一转为小写并去除首尾空格，防止微小差异导致指纹变化。
    """
    return socket.gethostname().strip().lower()


# BIOS 序列号的常见占位符（不同 OEM 厂商使用不同占位符，需过滤）
_BIOS_PLACEHOLDERS = frozenset({
    'default string',
    'to be filled by o.e.m.',
    'to be filled by o.e.m./system product name',
    'none',
    'system serial number',
    'system product name',
    'not defined',
    'unknown',
    '0',
})


def get_bios_serial() -> str:
    """读取 BIOS 序列号（TD-07: 通过 PowerShell CIM 增强指纹维度）。

    P1-3: 从 wmic 迁移到 PowerShell CIM（Get-CimInstance），
    因为 wmic 在 Windows 11 22H2+ 已弃用，未来版本将被移除。

    失败时返回空字符串，不阻断机器码生成（其他三维度仍有效）。
    过滤 OEM 常见占位符（"Default string" 等）。

    Returns:
        BIOS 序列号字符串，或空字符串（获取失败/占位符/非 Windows）
    """
    if sys.platform != 'win32':
        return ''
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             '(Get-CimInstance Win32_BIOS).SerialNumber'],
            capture_output=True, text=True, timeout=5,
            creationflags=0x08000000,  # CREATE_NO_WINDOW，避免弹出黑框
        )
        serial = result.stdout.strip()
        if serial and serial.lower() not in _BIOS_PLACEHOLDERS:
            return serial
        return ''
    except (OSError, subprocess.SubprocessError, ValueError):
        return ''


def compute_machine_code(machine_guid: str, volume_serial: str,
                          computer_name: str, bios_serial: str = '') -> str:
    """计算机器码 = SHA-256(guid|volume|name|bios).hex()。

    Args:
        machine_guid: 从注册表读到的 MachineGuid
        volume_serial: C 盘卷序列号（8 字符大写 hex）
        computer_name: 计算机名
        bios_serial: BIOS 序列号（TD-07: 第 4 维度，获取失败时为空字符串）

    Returns:
        64 字符小写 hex 字符串
    """
    raw = f"{machine_guid}|{volume_serial}|{computer_name}|{bios_serial}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def get_machine_code_or_none() -> Optional[str]:  # TD-13: 统一为 Optional[str]
    """获取本机机器码，失败返回 None（用于降级试用）。

    采集四个维度：MachineGuid + C盘卷序列号 + 计算机名 + BIOS序列号。
    前 3 个维度任一获取失败，整体降级返回 None。
    BIOS 序列号获取失败时用空字符串（不阻断，其他维度仍有效）。

    Returns:
        机器码字符串，或 None
    """
    try:
        guid = get_machine_guid()
        volume = get_volume_serial()
        name = get_computer_name()
        bios = get_bios_serial()  # 失败时返回 ''，不抛异常
        return compute_machine_code(guid, volume, name, bios)
    except (UnsupportedOSError, OSError) as e:
        logger.warning("采集机器指纹失败，降级试用模式: %s", e)
        return None
