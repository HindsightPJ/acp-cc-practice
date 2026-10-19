"""license 授权全链路测试（H4：替代被 .gitignore 排除的三个集成测试的客户端语义）。

背景：tests/integration 的 test_full_flow / test_cross_machine / test_key_stability
源文件被 .gitignore 排除、从未入 git——"签发 → 验签 → 解密题库"这条真实密码学链
在 CI 从未跑过。本文件在 unit 层用测试 Ed25519 密钥对 + 测试 Fernet key，在
tmp_path 重建完整链路，覆盖三者的核心语义：

1. test_full_authorize_flow：签发 → 落盘 license.dat → 验签 AUTHORIZED →
   用 K 解密 questions.enc → 题目正确解析
2. test_cross_machine_fails：A 机的注册码在 B 机 → WRONG_MACHINE → 降级试用，
   且 license.dat 保留（非损坏类失败不备份，便于用户重试）
3. test_trial_loads_without_license：无授权时 trial 题库直接加载（新用户首启路径）
4. test_key_stability：K 不变、题库更新（重新加密）后旧注册码仍有效
5. test_production_public_key_is_valid：生产公钥可解析为合法 Ed25519 点
   （防抄错/截断；真实私钥配对属作者侧职责，author_tools 不入库）

_make_license 与 test_verifier 共用同一签发实现，避免两份签发逻辑漂移。
"""

import glob
import json
import os
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet

from data_manager import DataManager
from license import LicenseStatus
from license.public_key import ED25519_PUBLIC_KEY_HEX
from license.verifier import LicenseVerifier
from test_verifier import _make_license

MACHINE_A = "a" * 64
MACHINE_B = "b" * 64

_SAMPLE_QUESTIONS = [
    {
        "number": 1,
        "content": "阿里云 OSS 的存储类型不包括？",
        "options": [
            {"letter": "A", "text": "标准存储"},
            {"letter": "B", "text": "低频访问存储"},
            {"letter": "C", "text": "归档存储"},
            {"letter": "D", "text": "高速缓存存储"},
        ],
        "answer": "D",
        "type": "single",
        "explanation": "OSS 提供标准、低频访问、归档、冷归档、深度冷归档存储类型。",
    },
    {
        "number": 2,
        "content": "以下哪些属于阿里云 VPC 内的组件？",
        "options": [
            {"letter": "A", "text": "交换机"},
            {"letter": "B", "text": "路由器"},
            {"letter": "C", "text": "对象存储 OSS"},
            {"letter": "D", "text": "安全组"},
        ],
        "answer": "ABD",
        "type": "multiple",
        "explanation": "OSS 是全局服务，不属于 VPC 内组件。",
    },
]

_NEW_QUESTION = {
    "number": 3,
    "content": "SLB 的全称是？",
    "options": [
        {"letter": "A", "text": "Server Load Balancing"},
        {"letter": "B", "text": "Simple Log Base"},
        {"letter": "C", "text": "Storage Location Bucket"},
        {"letter": "D", "text": "Security License Base"},
    ],
    "answer": "A",
    "type": "single",
    "explanation": "SLB = Server Load Balancing，即阿里云负载均衡。",
}


@pytest.fixture
def ed25519_keypair():
    """测试用 Ed25519 密钥对 + Fernet key（K），全部随机生成、不落盘。"""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    priv = Ed25519PrivateKey.generate()
    priv_bytes = priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_bytes = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return {
        "k": Fernet.generate_key().decode(),
        "private_hex": priv_bytes.hex(),
        "public_hex": pub_bytes.hex(),
    }


@pytest.fixture
def data_dirs(tmp_path):
    """搭建 base（只读题库目录）/ user（可写数据目录）双目录，返回 (base_dir, user_data_dir)。"""
    base_dir = tmp_path / "base"
    user_data = tmp_path / "user"
    (base_dir / "data").mkdir(parents=True)
    user_data.mkdir(parents=True)
    return str(base_dir), str(user_data)


def _write_trial_bank(base_dir: str) -> None:
    with open(os.path.join(base_dir, "data", "questions_trial.json"), "w", encoding="utf-8") as f:
        json.dump(_SAMPLE_QUESTIONS, f, ensure_ascii=False)


def _write_encrypted_bank(base_dir: str, fernet_key: str, questions=None) -> None:
    """用 K 加密题库写入 questions.enc（模拟作者侧 encrypt_questions 产物）。"""
    payload = _SAMPLE_QUESTIONS if questions is None else questions
    ciphertext = Fernet(fernet_key.encode()).encrypt(
        json.dumps(payload, ensure_ascii=False).encode("utf-8")
    )
    with open(os.path.join(base_dir, "data", "questions.enc"), "wb") as f:
        f.write(ciphertext)


def test_full_authorize_flow(data_dirs, ed25519_keypair, monkeypatch):
    """完整链路：签发 → 落盘 → 验签 AUTHORIZED → 解密 questions.enc → 解析题目。"""
    base_dir, user_data = data_dirs
    _write_trial_bank(base_dir)
    _write_encrypted_bank(base_dir, ed25519_keypair["k"])
    monkeypatch.setattr("license.verifier.ED25519_PUBLIC_KEY_HEX", ed25519_keypair["public_hex"])

    license_code = _make_license(MACHINE_A, ed25519_keypair["k"], ed25519_keypair["private_hex"])

    verifier = LicenseVerifier(data_dir=user_data)
    assert verifier.save_license(license_code) is True

    with patch("license.verifier.get_machine_code_or_none", return_value=MACHINE_A):
        status, k, failed = verifier.check_local_license()
    assert status == LicenseStatus.AUTHORIZED
    assert failed is False
    assert k == ed25519_keypair["k"]

    manager = DataManager(base_dir, user_data_dir=user_data)
    questions = manager.load_full_questions(k)
    assert [q.number for q in questions] == [1, 2]
    assert questions[0].answer == "D"
    assert questions[1].type == "multiple"


def test_cross_machine_fails(data_dirs, ed25519_keypair, monkeypatch):
    """A 机的注册码在 B 机 → WRONG_MACHINE → 降级试用；license.dat 保留可重试。"""
    base_dir, user_data = data_dirs
    _write_trial_bank(base_dir)
    _write_encrypted_bank(base_dir, ed25519_keypair["k"])
    monkeypatch.setattr("license.verifier.ED25519_PUBLIC_KEY_HEX", ed25519_keypair["public_hex"])

    license_code = _make_license(MACHINE_A, ed25519_keypair["k"], ed25519_keypair["private_hex"])
    verifier = LicenseVerifier(data_dir=user_data)
    assert verifier.save_license(license_code) is True

    with patch("license.verifier.get_machine_code_or_none", return_value=MACHINE_B):
        status, k, failed = verifier.check_local_license()
    assert status == LicenseStatus.TRIAL
    assert k is None
    assert failed is True
    # WRONG_MACHINE 非损坏类失败：保留原文件便于用户重试，不生成 .corrupt 备份
    assert os.path.exists(verifier.license_file)
    assert glob.glob(os.path.join(user_data, "license.dat.corrupt-*")) == []

    # 降级路径：拿不到 K 时加载 trial 题库
    manager = DataManager(base_dir, user_data_dir=user_data)
    assert [q.number for q in manager.load_trial_questions()] == [1, 2]


def test_trial_loads_without_license(data_dirs):
    """无 license.dat → trial 题库直接加载（新用户首启路径）。"""
    base_dir, user_data = data_dirs
    _write_trial_bank(base_dir)
    manager = DataManager(base_dir, user_data_dir=user_data)
    assert [q.number for q in manager.load_trial_questions()] == [1, 2]


def test_key_stability(data_dirs, ed25519_keypair, monkeypatch):
    """K 不变时题库更新（重新加密），旧注册码仍能解密新题库。"""
    base_dir, user_data = data_dirs
    _write_trial_bank(base_dir)
    _write_encrypted_bank(base_dir, ed25519_keypair["k"])
    monkeypatch.setattr("license.verifier.ED25519_PUBLIC_KEY_HEX", ed25519_keypair["public_hex"])

    license_code = _make_license(MACHINE_A, ed25519_keypair["k"], ed25519_keypair["private_hex"])
    verifier = LicenseVerifier(data_dir=user_data)
    assert verifier.save_license(license_code) is True

    # 题库更新：追加一题，用同一 K 重新加密
    _write_encrypted_bank(base_dir, ed25519_keypair["k"], _SAMPLE_QUESTIONS + [_NEW_QUESTION])

    with patch("license.verifier.get_machine_code_or_none", return_value=MACHINE_A):
        status, k, _ = verifier.check_local_license()
    assert status == LicenseStatus.AUTHORIZED

    manager = DataManager(base_dir, user_data_dir=user_data)
    assert [q.number for q in manager.load_full_questions(k)] == [1, 2, 3]


def test_production_public_key_is_valid():
    """生产公钥是可解析的合法 Ed25519 点（防抄错/截断；私钥配对属作者侧职责）。"""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    raw = bytes.fromhex(ED25519_PUBLIC_KEY_HEX)
    assert len(raw) == 32
    Ed25519PublicKey.from_public_bytes(raw)  # 非法点会抛 ValueError
