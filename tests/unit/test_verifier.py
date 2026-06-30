"""verifier.py 单元测试。"""
import base64
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from license import LicenseError, LicenseStatus  # pylint: disable=wrong-import-position
from license import verifier  # pylint: disable=wrong-import-position
from license.crypto_utils import derive_dk  # pylint: disable=wrong-import-position


def _make_license(machine_code: str, key_k: str, private_key_hex: str) -> str:
    """测试用：生成注册码（与 verifier.py 的解密逻辑严格对应）。

    注册码 = base64( signature(64) || salt(16) || encrypted_K(72) )
      encrypted_K = nonce(12) + AES-256-GCM(nonce, K, DK, aad=salt)
      DK = PBKDF2(machine_code, salt, 200000)
    """
    salt = os.urandom(16)
    dk = derive_dk(machine_code, salt)
    nonce = os.urandom(12)
    aesgcm = AESGCM(dk)
    # GCM nonce=nonce, AAD=salt
    encrypted_k = nonce + aesgcm.encrypt(nonce, key_k.encode('utf-8'), salt)

    private_bytes = bytes.fromhex(private_key_hex)
    priv = Ed25519PrivateKey.from_private_bytes(private_bytes)
    signature = priv.sign(salt + encrypted_k)

    return base64.b64encode(signature + salt + encrypted_k).decode('utf-8')


@pytest.fixture
def setup_keys():
    """生成测试用 K + Ed25519 密钥对。"""
    from cryptography.hazmat.primitives import serialization
    key_k = Fernet.generate_key().decode()
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    priv_bytes = priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_bytes = pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return {
        'k': key_k,
        'private_hex': priv_bytes.hex(),
        'public_hex': pub_bytes.hex(),
    }


@pytest.fixture
def patch_public_key(setup_keys, monkeypatch):
    """把 verifier 的公钥常量替换为测试公钥。"""
    monkeypatch.setattr(
        'license.verifier.ED25519_PUBLIC_KEY_HEX',
        setup_keys['public_hex'],
    )


def test_verify_success(patch_public_key, setup_keys):
    """正确机器码 + 正确注册码 → 返回 AUTHORIZED + K。"""
    machine_code = 'a' * 64
    license_code = _make_license(machine_code, setup_keys['k'], setup_keys['private_hex'])

    with patch('license.verifier.get_machine_code_or_none', return_value=machine_code):
        status, k, _ = verifier.verify(license_code)
    assert status == LicenseStatus.AUTHORIZED
    assert k == setup_keys['k']


def test_verify_wrong_machine(patch_public_key, setup_keys):
    """注册码不属于本机 → WRONG_MACHINE。"""
    # 用机器 A 的码生成注册码
    license_code = _make_license('a' * 64, setup_keys['k'], setup_keys['private_hex'])
    # 但本机是机器 B
    with patch('license.verifier.get_machine_code_or_none', return_value='b' * 64):
        result = verifier.verify(license_code)
    assert result[0] == LicenseStatus.TRIAL
    assert result[1] is None
    assert result[2] == LicenseError.WRONG_MACHINE


def test_verify_invalid_signature(patch_public_key, setup_keys):
    """验签失败 → INVALID_SIGNATURE。

    在 raw bytes 层面翻转中段字节（保持长度不变），确定性触发签名失败。
    """
    machine_code = 'a' * 64
    license_code = _make_license(machine_code, setup_keys['k'], setup_keys['private_hex'])

    # base64 解码 → 翻转 signature 的中段字节 → 重新编码
    raw = bytearray(base64.b64decode(license_code))
    raw[32] ^= 0xFF  # 翻转 signature 中段一字节
    tampered = base64.b64encode(bytes(raw)).decode('utf-8')

    with patch('license.verifier.get_machine_code_or_none', return_value=machine_code):
        result = verifier.verify(tampered)
    assert result[0] == LicenseStatus.TRIAL
    assert result[2] == LicenseError.INVALID_SIGNATURE


def test_verify_fingerprint_failed(patch_public_key, setup_keys):
    """指纹采集失败 → FINGERPRINT_FAILED。"""
    machine_code = 'a' * 64
    license_code = _make_license(machine_code, setup_keys['k'], setup_keys['private_hex'])
    with patch('license.verifier.get_machine_code_or_none', return_value=None):
        result = verifier.verify(license_code)
    assert result[0] == LicenseStatus.FINGERPRINT_FAILED
    assert result[1] is None


def test_verify_corrupt_not_base64(patch_public_key):
    """非合法 base64 → CORRUPT_LICENSE_FILE。"""
    result = verifier.verify('!!!not-base64!!!')
    assert result[0] == LicenseStatus.TRIAL
    assert result[2] == LicenseError.CORRUPT_LICENSE_FILE


def test_verify_corrupt_wrong_length(patch_public_key):
    """base64 合法但长度不足 → CORRUPT_LICENSE_FILE。"""
    short = base64.b64encode(b'too short').decode('utf-8')
    result = verifier.verify(short)
    assert result[0] == LicenseStatus.TRIAL
    assert result[2] == LicenseError.CORRUPT_LICENSE_FILE


def test_verify_corrupt_non_string(patch_public_key):
    """非字符串输入 → CORRUPT_LICENSE_FILE。"""
    result = verifier.verify(None)  # type: ignore[arg-type]
    assert result[0] == LicenseStatus.TRIAL
    assert result[2] == LicenseError.CORRUPT_LICENSE_FILE


def test_check_local_license_no_file(tmp_path):
    """license.dat 不存在 → (TRIAL, None, False)。"""
    v = verifier.LicenseVerifier(data_dir=str(tmp_path))
    status, k, failed = v.check_local_license()
    assert status == LicenseStatus.TRIAL
    assert k is None
    assert failed is False


def test_check_local_license_with_valid_file(tmp_path, patch_public_key, setup_keys):
    """license.dat 存在且有效 → (AUTHORIZED, K, False)。"""
    machine_code = 'a' * 64
    license_code = _make_license(machine_code, setup_keys['k'], setup_keys['private_hex'])
    (tmp_path / 'license.dat').write_text(license_code, encoding='utf-8')

    v = verifier.LicenseVerifier(data_dir=str(tmp_path))
    with patch('license.verifier.get_machine_code_or_none', return_value=machine_code):
        status, k, failed = v.check_local_license()
    assert status == LicenseStatus.AUTHORIZED
    assert k == setup_keys['k']
    assert failed is False


def test_check_local_license_with_invalid_file(tmp_path, patch_public_key):
    """license.dat 存在但损坏 → (TRIAL, None, True) — UI 应告警。"""
    (tmp_path / 'license.dat').write_text('garbage-data', encoding='utf-8')
    v = verifier.LicenseVerifier(data_dir=str(tmp_path))
    status, k, failed = v.check_local_license()
    assert status == LicenseStatus.TRIAL
    assert k is None
    assert failed is True


def test_save_and_reload_license(tmp_path, patch_public_key, setup_keys):
    """save_license 写入后，check_local_license 应能读回并验证为 AUTHORIZED。"""
    machine_code = 'a' * 64
    license_code = _make_license(machine_code, setup_keys['k'], setup_keys['private_hex'])

    v = verifier.LicenseVerifier(data_dir=str(tmp_path))
    assert v.save_license(license_code) is True
    assert os.path.exists(v.license_file)

    with patch('license.verifier.get_machine_code_or_none', return_value=machine_code):
        status, k, failed = v.check_local_license()
    assert status == LicenseStatus.AUTHORIZED
    assert k == setup_keys['k']
    assert failed is False
