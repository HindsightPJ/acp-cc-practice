"""K 不变时，题库更新后旧注册码仍能解密新 enc。"""
import json
import sys
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'author_tools'))

import keygen  # pylint: disable=wrong-import-position
import encrypt_questions  # pylint: disable=wrong-import-position
import generate_license  # pylint: disable=wrong-import-position
from license import verifier, LicenseStatus  # pylint: disable=wrong-import-position
from data_manager import DataManager  # pylint: disable=wrong-import-position


@pytest.fixture
def setup_env(tmp_path, monkeypatch):
    keys = keygen.generate_keys()
    env_path = tmp_path / '.env'
    keygen.write_env(keys, str(env_path))

    (tmp_path / 'data').mkdir()
    monkeypatch.setattr(encrypt_questions, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(encrypt_questions, 'ENV_FILE', str(env_path))
    monkeypatch.setattr(encrypt_questions, 'DATA_DIR', str(tmp_path / 'data'))
    monkeypatch.setattr(encrypt_questions, 'QUESTIONS_JSON', str(tmp_path / 'data' / 'questions.json'))
    monkeypatch.setattr(encrypt_questions, 'QUESTIONS_ENC', str(tmp_path / 'data' / 'questions.enc'))
    monkeypatch.setattr(encrypt_questions, 'QUESTIONS_TRIAL', str(tmp_path / 'data' / 'questions_trial.json'))
    monkeypatch.setattr(encrypt_questions, 'QUESTIONS_META', str(tmp_path / 'data' / 'questions_meta.json'))
    monkeypatch.setattr(generate_license, 'ENV_FILE', str(env_path))
    monkeypatch.setattr(generate_license, 'ISSUED_LICENSES', str(tmp_path / 'issued.json'))
    monkeypatch.setattr(verifier, 'ED25519_PUBLIC_KEY_HEX', keys['ed25519_public_key'])
    return {'tmp_path': tmp_path, 'keys': keys}


def _write_questions(path, count):
    qs = [
        {'number': i, 'content': f'题 {i}', 'options': [], 'answer': 'A', 'type': 'single', 'explanation': ''}
        for i in range(1, count + 1)
    ]
    path.write_text(json.dumps(qs, ensure_ascii=False), encoding='utf-8')


def test_key_stability(setup_env, monkeypatch):
    """K 不变时题库更新，旧注册码仍有效。"""
    tmp_path = setup_env['tmp_path']
    keys = setup_env['keys']
    machine_code = 'a' * 64

    # 1. 25 题加密
    _write_questions(tmp_path / 'data' / 'questions.json', 25)
    encrypt_questions.main()

    # 2. 为该机器签发注册码
    license_code = generate_license.generate_license_for_machine_code(machine_code)

    # 3. 题库更新到 30 题（K 不变）
    _write_questions(tmp_path / 'data' / 'questions.json', 30)
    encrypt_questions.main()

    # 4. 旧注册码仍能解出新 enc
    monkeypatch.setattr(verifier, 'get_machine_code_or_none', lambda: machine_code)
    status, k, _ = verifier.verify(license_code)
    assert status == LicenseStatus.AUTHORIZED
    assert k == keys['questions_master_key']

    dm = DataManager(base_dir=str(tmp_path))
    full_qs = dm.load_full_questions(k)
    assert len(full_qs) == 30  # 新题数
