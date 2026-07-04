"""generate_license.py 单元测试。"""
import base64
import json
import os
import sys
from unittest.mock import Mock

import pytest

import generate_license
import keygen


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

def test_record_issued_atomic_write_failure(setup_env, monkeypatch, tmp_path):
    """TD-09: 写入失败时应抛异常且不留 tmp 文件。"""
    bad_path = str(tmp_path / 'nonexistent_dir' / 'issued.json')
    monkeypatch.setattr(generate_license, 'ISSUED_LICENSES', bad_path)
    with pytest.raises(OSError):
        generate_license.record_issued('a' * 64, "test")
    # tmp 文件不应残留
    assert not os.path.exists(bad_path + '.tmp')


# ---------- load_author_keys 边界测试 ----------


def test_load_author_keys_returns_keys(tmp_path, monkeypatch):
    """.env 存在且包含所需 key 时返回 dict。"""
    keys = keygen.generate_keys()
    env_path = tmp_path / '.env'
    env_path.write_text(
        f"QUESTIONS_MASTER_KEY={keys['questions_master_key']}\n"
        f"ED25519_PRIVATE_KEY={keys['ed25519_private_key']}\n",
        encoding='utf-8',
    )
    monkeypatch.setattr(generate_license, 'ENV_FILE', str(env_path))

    result = generate_license.load_author_keys()

    assert result == {
        'k': keys['questions_master_key'],
        'private_hex': keys['ed25519_private_key'],
    }


def test_load_author_keys_exits_when_env_missing(tmp_path, monkeypatch):
    """.env 缺失时调用 sys.exit(1)。"""
    monkeypatch.setattr(
        generate_license, 'ENV_FILE', str(tmp_path / 'missing.env')
    )
    mock_exit = Mock(side_effect=SystemExit)
    monkeypatch.setattr(sys, 'exit', mock_exit)

    with pytest.raises(SystemExit):
        generate_license.load_author_keys()

    mock_exit.assert_called_once_with(1)


def test_load_author_keys_exits_when_keys_missing(tmp_path, monkeypatch):
    """.env 缺少 QUESTIONS_MASTER_KEY 或 ED25519_PRIVATE_KEY 时调用 sys.exit(1)。"""
    env_path = tmp_path / '.env'
    env_path.write_text('QUESTIONS_MASTER_KEY=only-master-key\n', encoding='utf-8')
    monkeypatch.setattr(generate_license, 'ENV_FILE', str(env_path))
    mock_exit = Mock(side_effect=SystemExit)
    monkeypatch.setattr(sys, 'exit', mock_exit)

    with pytest.raises(SystemExit):
        generate_license.load_author_keys()

    mock_exit.assert_called_once_with(1)


# ---------- record_issued 去重与损坏文件处理 ----------


def test_record_issued_deduplicates_by_machine_code(setup_env):
    """同一 machine_code 重复记录时只保留最新一条。"""
    machine_code = 'a' * 64
    generate_license.record_issued(machine_code, "first-note")
    generate_license.record_issued(machine_code, "updated-note")

    with open(generate_license.ISSUED_LICENSES, 'r', encoding='utf-8') as f:
        records = json.load(f)

    assert len(records) == 1
    assert records[0]['machine_code'] == machine_code
    assert records[0]['note'] == "updated-note"


def test_record_issued_handles_corrupt_existing_file(setup_env, tmp_path, monkeypatch):
    """已有 issued_licenses.json 损坏时备份并重新写入新记录。"""
    monkeypatch.setattr(generate_license, 'ISSUED_LICENSES', str(tmp_path / 'issued_licenses.json'))
    corrupt_file = tmp_path / 'issued_licenses.json'
    corrupt_file.write_text('this is not json', encoding='utf-8')

    generate_license.record_issued('a' * 64, "after-corrupt")

    # 原损坏文件应被备份
    backups = list(tmp_path.glob('issued_licenses.json.corrupt-*'))
    assert len(backups) == 1
    assert backups[0].read_text(encoding='utf-8') == 'this is not json'

    # 新记录正确写入
    with open(generate_license.ISSUED_LICENSES, 'r', encoding='utf-8') as f:
        records = json.load(f)
    assert len(records) == 1
    assert records[0]['machine_code'] == 'a' * 64
