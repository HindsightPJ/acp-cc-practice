"""采集本机机器指纹。

平台：Windows
非 Windows：抛 UnsupportedOSError，由调用方降级为试用模式。

机器码 = SHA-256(MachineGuid + "|" + VolumeSerial(C:) + "|" + ComputerName).hex()
三维度组合，单一维度克隆（如磁盘镜像）不足以绕过。
此值会显示给用户复制，并作为 PBKDF2 的 password 输入。
"""
import hashlib
import os
import socket
import sys
import logging

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
        return value
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

    优先用环境变量 COMPUTERNAME，fallback 到 socket.gethostname()。
    """
    return os.environ.get('COMPUTERNAME') or socket.gethostname()


def compute_machine_code(machine_guid: str, volume_serial: str, computer_name: str) -> str:
    """计算机器码 = SHA-256(guid|volume|name).hex()。

    Args:
        machine_guid: 从注册表读到的 MachineGuid
        volume_serial: C 盘卷序列号（8 字符大写 hex）
        computer_name: 计算机名

    Returns:
        64 字符小写 hex 字符串
    """
    raw = f"{machine_guid}|{volume_serial}|{computer_name}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def get_machine_code_or_none() -> str | None:
    """获取本机机器码，失败返回 None（用于降级试用）。

    采集三个维度：MachineGuid + C盘卷序列号 + 计算机名。
    任一维度获取失败，整体降级返回 None。

    Returns:
        机器码字符串，或 None
    """
    try:
        guid = get_machine_guid()
        volume = get_volume_serial()
        name = get_computer_name()
        return compute_machine_code(guid, volume, name)
    except (UnsupportedOSError, OSError) as e:
        logger.warning("采集机器指纹失败，降级试用模式: %s", e)
        return None
