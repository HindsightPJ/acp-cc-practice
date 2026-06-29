"""generate_license.py 单元测试。"""
import base64
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'author_tools'))
import generate_license  # pylint: disable=wrong-import-position
import keygen  # pylint: disable=wrong-import-position


@pytest.fixture
def setup_env(tmp_path, monkeypatch):
    """搭建临时 .env + issued_licenses.json 路径。"""
    keys = keygen.generate_keys()
    env_path = tmp_path / '.env'
    keygen.write_env(keys, str(env_path))

    monkeypatch.setattr(generate_license, 'ENV_FILE', str(env_path))
    monkeypatch.setattr(generate_license, 'ISSUED_LICENSES', str(tmp_path / 'issued_licenses.json'))
    return keys


def test_generate_license_returns_valid_format(setup_env):
    """generate_license_for_machine_code 返回的注册码应能 base64 解码为 152 字节。

    152 = 64(signature) + 16(salt) + 72(encrypted_K)
    encrypted_K = 12(nonce) + 44(K base64 UTF-8) + 16(GCM tag)
    """
    machine_code = 'a' * 64
    license_code = generate_license.generate_license_for_machine_code(machine_code)

    raw = base64.b64decode(license_code)
    assert len(raw) == 152  # 64 + 16 + 72


def test_generated_license_can_be_verified(setup_env, monkeypatch):
    """生成的注册码应能被 verifier 验证通过（端到端集成）。"""
    machine_code = 'a' * 64
    license_code = generate_license.generate_license_for_machine_code(machine_code)

    # 用 verifier 验证
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from license import verifier
    monkeypatch.setattr(verifier, 'ED25519_PUBLIC_KEY_HEX', setup_env['ed25519_public_key'])
    monkeypatch.setattr(verifier, 'get_machine_code_or_none', lambda: machine_code)

    status, k, err = verifier.verify(license_code)
    assert status.value == 'authorized'
    assert k == setup_env['questions_master_key']
    assert err is None


def test_record_issued_license_appends(setup_env):
    """record_issued 应追加到 issued_licenses.json。"""
    machine_code = 'a' * 64
    generate_license.record_issued(machine_code, "test-user")

    with open(generate_license.ISSUED_LICENSES, 'r', encoding='utf-8') as f:
        records = json.load(f)
    assert len(records) == 1
    assert records[0]['machine_code'] == machine_code
    assert records[0]['note'] == "test-user"
    assert 'date' in records[0]


def test_record_issued_appends_multiple(setup_env):
    """多次 record_issued 应追加而非覆盖。"""
    generate_license.record_issued('a' * 64, "user-a")
    generate_license.record_issued('b' * 64, "user-b")

    with open(generate_license.ISSUED_LICENSES, 'r', encoding='utf-8') as f:
        records = json.load(f)
    assert len(records) == 2
    assert records[0]['machine_code'] == 'a' * 64
    assert records[1]['machine_code'] == 'b' * 64
