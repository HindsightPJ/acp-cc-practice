"""注册码验证模块。

注册码格式：base64( signature || salt || encrypted_K )
  signature   = Ed25519_sign( salt || encrypted_K, private_key )   64 字节
  salt        = 16 字节随机盐（仅作 PBKDF2 salt 与 GCM AAD）
  encrypted_K = nonce(12) + AES-256-GCM(nonce, K, DK, aad=salt)    72 字节
                其中 K 为 Fernet key 的 base64 字符串（44 字节 UTF-8）
                nonce 为独立 12 字节随机值，参与签名与 GCM 运算

验证流程：
  1. base64 解码
  2. 拆分 signature || salt || encrypted_K（严格长度校验）
  3. Ed25519 验签（用内置公钥）
  4. 采集本机指纹 F
  5. DK = PBKDF2(F, salt, 200000)
  6. K = AES-256-GCM-Decrypt(nonce, ciphertext_with_tag, aad=salt)
     （GCM tag 验证指纹：机器码错误 → DK 错误 → tag 不匹配 → WRONG_MACHINE）
"""
import base64
import os
import logging
from typing import Optional, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag, InvalidSignature

from license import LicenseError, LicenseStatus
from license.fingerprint import get_machine_code_or_none
from license.public_key import ED25519_PUBLIC_KEY_HEX
from license.crypto_utils import derive_dk

logger = logging.getLogger(__name__)


# 注册码各部分字节长度
SIGNATURE_LEN = 64
SALT_LEN = 16
NONCE_LEN = 12           # AES-GCM nonce（NIST 推荐的 96-bit）
GCM_TAG_LEN = 16
K_LEN = 44               # Fernet key 的 base64 字符串 UTF-8 编码长度
ENCRYPTED_K_LEN = NONCE_LEN + K_LEN + GCM_TAG_LEN  # 12 + 44 + 16 = 72
EXPECTED_RAW_LEN = SIGNATURE_LEN + SALT_LEN + ENCRYPTED_K_LEN  # 152



def verify(license_code: str) -> Tuple[LicenseStatus, Optional[str], Optional[LicenseError]]:
    """验证注册码。

    Args:
        license_code: base64 编码的注册码字符串

    Returns:
        (status, K, error)
        - 成功：(AUTHORIZED, K, None)
        - 失败：(TRIAL 或 FINGERPRINT_FAILED, None, 错误码)
    """
    # 1. base64 解码（validate=True 拒绝非字母表字符）
    if not isinstance(license_code, str):
        return (LicenseStatus.TRIAL, None, LicenseError.CORRUPT_LICENSE_FILE)
    try:
        raw = base64.b64decode(license_code, validate=True)
    except (ValueError, TypeError):
        return (LicenseStatus.TRIAL, None, LicenseError.CORRUPT_LICENSE_FILE)

    # 2. 拆分 - 严格长度校验（152 字节）
    if len(raw) != EXPECTED_RAW_LEN:
        return (LicenseStatus.TRIAL, None, LicenseError.CORRUPT_LICENSE_FILE)
    signature = raw[:SIGNATURE_LEN]
    salt = raw[SIGNATURE_LEN:SIGNATURE_LEN + SALT_LEN]
    encrypted_k = raw[SIGNATURE_LEN + SALT_LEN:]

    # 3. Ed25519 验签
    try:
        public_key_bytes = bytes.fromhex(ED25519_PUBLIC_KEY_HEX)
        pub = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        pub.verify(signature, salt + encrypted_k)
    except (InvalidSignature, ValueError):
        return (LicenseStatus.TRIAL, None, LicenseError.INVALID_SIGNATURE)

    # 4. 采集本机指纹
    machine_code = get_machine_code_or_none()
    if machine_code is None:
        return (LicenseStatus.FINGERPRINT_FAILED, None, None)

    # 5. 派生 DK
    dk = derive_dk(machine_code, salt)

    # 6. AES-GCM 解密 K
    #    encrypted_k = nonce(12) + ciphertext_with_tag(60)
    #    GCM nonce = encrypted_k 的前 12 字节，AAD = salt
    nonce = encrypted_k[:NONCE_LEN]
    ciphertext_with_tag = encrypted_k[NONCE_LEN:]
    aesgcm = AESGCM(dk)
    try:
        k_bytes = aesgcm.decrypt(nonce, ciphertext_with_tag, salt)
    except InvalidTag:
        return (LicenseStatus.TRIAL, None, LicenseError.WRONG_MACHINE)

    try:
        k = k_bytes.decode('utf-8')
    except UnicodeDecodeError:
        return (LicenseStatus.TRIAL, None, LicenseError.CORRUPT_LICENSE_FILE)
    return (LicenseStatus.AUTHORIZED, k, None)


class LicenseVerifier:
    """注册码验证器，封装 license.dat 持久化逻辑。"""

    def __init__(self, data_dir: str) -> None:
        self.license_file: str = os.path.join(data_dir, 'license.dat')

    def check_local_license(self) -> Tuple[LicenseStatus, Optional[str], bool]:
        """检查本地 license.dat。

        Returns:
            (status, K, had_failure)
            - 无文件：(TRIAL, None, False) — 静默试用
            - 有文件且成功：(AUTHORIZED, K, False)
            - 有文件但失败：(TRIAL, None, True) — UI 应告警用户
        """
        if not os.path.exists(self.license_file):
            return (LicenseStatus.TRIAL, None, False)

        try:
            with open(self.license_file, 'r', encoding='utf-8') as f:
                license_code = f.read().strip()
        except OSError as e:
            logger.warning("读取 license.dat 失败: %s", e)
            return (LicenseStatus.TRIAL, None, True)

        status, k, err = verify(license_code)
        if status == LicenseStatus.AUTHORIZED:
            return (status, k, False)
        logger.warning("license.dat 验证失败，降级试用: %s", err)
        return (LicenseStatus.TRIAL, None, True)

    def save_license(self, license_code: str) -> bool:
        """持久化注册码到 license.dat。

        Returns:
            True 保存成功，False 保存失败（权限等）
        """
        try:
            with open(self.license_file, 'w', encoding='utf-8') as f:
                f.write(license_code)
            return True
        except (OSError, PermissionError) as e:
            logger.error("保存 license.dat 失败: %s", e)
            return False
