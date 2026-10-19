"""tests/unit 共享 fixtures（PySide6 offscreen 版）。

P6 迁移：tkinter session 级 Tk 根实例 → Qt offscreen 平台。
- 环境变量必须在首个 QApplication 创建前设置，故置于模块顶层；
- QT_QPA_FONTDIR：offscreen 不扫系统字体，不指定会让文字渲染为空框；
- pytest-qt 提供 session 级 qapp 与 qtbot，此处不再自定义 QApplication fixture。
"""

import base64
import os

# 必须在任何 QApplication 实例化之前生效（conftest import 时点早于所有测试收集）
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest
from PySide6.QtWidgets import QMessageBox
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from license.crypto_utils import derive_dk


@pytest.fixture(autouse=True)
def _mute_message_boxes(monkeypatch):
    """静音 QMessageBox 全部静态弹窗：模态 exec 在 offscreen 无头进程下永久阻塞。

    默认 question 返回 No（保守：写操作类确认一律拒绝）；
    需要 Yes 或断言弹窗文案的用例在测试体内自行 monkeypatch 覆盖
    （fixture setup 先于测试体执行，后设置的 mock 生效）。
    """
    for name in ("information", "warning", "critical", "about"):
        monkeypatch.setattr(QMessageBox, name, lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)


# ---------- 授权测试共享夹具（从 test_verifier 上移，供 license_dialog 等复用） ----------


def _make_license(machine_code: str, key_k: str, private_key_hex: str) -> str:
    """测试用：生成注册码（与 verifier.py 的解密逻辑严格对应）。

    注册码 = base64( signature(64) || salt(16) || encrypted_K(72) )
      encrypted_K = nonce(12) + AES-256-GCM(nonce, K, DK, aad=salt)
      DK = PBKDF2(machine_code, salt, 600000)
    """
    salt = os.urandom(16)
    dk = derive_dk(machine_code, salt)
    nonce = os.urandom(12)
    aesgcm = AESGCM(dk)
    # GCM nonce=nonce, AAD=salt
    encrypted_k = nonce + aesgcm.encrypt(nonce, key_k.encode("utf-8"), salt)

    private_bytes = bytes.fromhex(private_key_hex)
    priv = Ed25519PrivateKey.from_private_bytes(private_bytes)
    signature = priv.sign(salt + encrypted_k)

    return base64.b64encode(signature + salt + encrypted_k).decode("utf-8")


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
        "k": key_k,
        "private_hex": priv_bytes.hex(),
        "public_hex": pub_bytes.hex(),
    }


@pytest.fixture
def patch_public_key(setup_keys, monkeypatch):
    """把 verifier 的公钥常量替换为测试公钥。"""
    monkeypatch.setattr(
        "license.verifier.ED25519_PUBLIC_KEY_HEX",
        setup_keys["public_hex"],
    )
