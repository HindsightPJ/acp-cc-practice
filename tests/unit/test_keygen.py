"""keygen.py 单元测试。"""
import os
import sys
import tempfile
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

# 把 author_tools 加入 import 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'author_tools'))
import keygen  # pylint: disable=wrong-import-position


def test_generate_keys_returns_valid_fernet_key():
    """生成的 K 应是有效的 Fernet key。"""
    keys = keygen.generate_keys()
    f = Fernet(keys['questions_master_key'].encode())
    # 能加密解密即视为有效
    token = f.encrypt(b"test")
    assert f.decrypt(token) == b"test"


def test_generate_keys_returns_ed25519_keypair():
    """生成的 Ed25519 密钥对应能验签。"""
    keys = keygen.generate_keys()
    pub = Ed25519PublicKey.from_public_bytes(
        bytes.fromhex(keys['ed25519_public_key'])
    )
    # 用私钥签名，公钥验签
    private_bytes = bytes.fromhex(keys['ed25519_private_key'])
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    priv = Ed25519PrivateKey.from_private_bytes(private_bytes)
    sig = priv.sign(b"message")
    pub.verify(sig, b"message")  # 不抛异常即通过


def test_write_env_writes_all_keys(tmp_path):
    """write_env 应把所有密钥写入 .env 文件。"""
    keys = keygen.generate_keys()
    env_path = tmp_path / '.env'
    keygen.write_env(keys, str(env_path))
    content = env_path.read_text(encoding='utf-8')
    assert 'QUESTIONS_MASTER_KEY=' in content
    assert 'ED25519_PRIVATE_KEY=' in content
    assert 'ED25519_PUBLIC_KEY=' in content
