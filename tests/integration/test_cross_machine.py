"""跨机器使用注册码应失败。"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'author_tools'))

import keygen  # pylint: disable=wrong-import-position
import generate_license  # pylint: disable=wrong-import-position
from license import verifier, LicenseStatus, LicenseError  # pylint: disable=wrong-import-position


@pytest.fixture
def setup_keys_and_env(tmp_path, monkeypatch):
    keys = keygen.generate_keys()
    env_path = tmp_path / '.env'
    keygen.write_env(keys, str(env_path))
    monkeypatch.setattr(generate_license, 'ENV_FILE', str(env_path))
    monkeypatch.setattr(generate_license, 'ISSUED_LICENSES', str(tmp_path / 'issued.json'))
    monkeypatch.setattr(verifier, 'ED25519_PUBLIC_KEY_HEX', keys['ed25519_public_key'])
    return keys


def test_cross_machine_fails(setup_keys_and_env, monkeypatch):
    """A 机的注册码在 B 机应返回 WRONG_MACHINE。"""
    machine_a = 'a' * 64
    machine_b = 'b' * 64

    # 作者为 A 机签发
    license_code = generate_license.generate_license_for_machine_code(machine_a)

    # B 机验证
    monkeypatch.setattr(verifier, 'get_machine_code_or_none', lambda: machine_b)
    status, k, err = verifier.verify(license_code)
    assert status == LicenseStatus.TRIAL
    assert k is None
    assert err == LicenseError.WRONG_MACHINE
