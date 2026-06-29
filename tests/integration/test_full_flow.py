"""端到端集成测试：作者签发 → 客户端验证 → 解密全库。"""
import json
import sys
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

# 把 acp-cc-practice 根目录加入路径
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'author_tools'))

import keygen  # pylint: disable=wrong-import-position
import encrypt_questions  # pylint: disable=wrong-import-position
import generate_license  # pylint: disable=wrong-import-position
from license import verifier  # pylint: disable=wrong-import-position
from license import LicenseStatus  # pylint: disable=wrong-import-position
from data_manager import DataManager  # pylint: disable=wrong-import-position


@pytest.fixture
def full_setup(tmp_path, monkeypatch):
    """搭建完整工作目录：作者 .env + 题库 + 加密产物。"""
    # 1. 生成作者密钥
    keys = keygen.generate_keys()
    env_path = tmp_path / '.env'
    keygen.write_env(keys, str(env_path))

    # 2. 准备题库
    questions = [
        {
            'number': i,
            'content': f'题 {i}',
            'options': [{'letter': 'A', 'text': 'a'}, {'letter': 'B', 'text': 'b'}],
            'answer': 'A',
            'type': 'single',
            'explanation': '',
        }
        for i in range(1, 26)  # 25 题
    ]
    (tmp_path / 'data').mkdir()
    (tmp_path / 'data' / 'questions.json').write_text(
        json.dumps(questions, ensure_ascii=False), encoding='utf-8'
    )

    # 3. monkeypatch encrypt_questions 路径
    monkeypatch.setattr(encrypt_questions, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(encrypt_questions, 'ENV_FILE', str(env_path))
    monkeypatch.setattr(encrypt_questions, 'DATA_DIR', str(tmp_path / 'data'))
    monkeypatch.setattr(encrypt_questions, 'QUESTIONS_JSON', str(tmp_path / 'data' / 'questions.json'))
    monkeypatch.setattr(encrypt_questions, 'QUESTIONS_ENC', str(tmp_path / 'data' / 'questions.enc'))
    monkeypatch.setattr(encrypt_questions, 'QUESTIONS_TRIAL', str(tmp_path / 'data' / 'questions_trial.json'))
    monkeypatch.setattr(encrypt_questions, 'QUESTIONS_META', str(tmp_path / 'data' / 'questions_meta.json'))

    # 4. monkeypatch generate_license 路径
    monkeypatch.setattr(generate_license, 'ENV_FILE', str(env_path))
    monkeypatch.setattr(generate_license, 'ISSUED_LICENSES', str(tmp_path / 'issued_licenses.json'))

    # 5. monkeypatch verifier 公钥
    monkeypatch.setattr(verifier, 'ED25519_PUBLIC_KEY_HEX', keys['ed25519_public_key'])

    return {'tmp_path': tmp_path, 'keys': keys, 'questions': questions}


def test_full_authorize_flow(full_setup, monkeypatch):
    """完整流程：加密 → 签发 → 验证 → 解密。"""
    tmp_path = full_setup['tmp_path']
    keys = full_setup['keys']
    questions = full_setup['questions']

    # 1. 作者加密题库
    assert encrypt_questions.main() == 0

    # 2. 客户端机器码（mock）
    client_machine_code = 'a' * 64

    # 3. 作者为该机器签发注册码
    license_code = generate_license.generate_license_for_machine_code(client_machine_code)

    # 4. 客户端验证注册码
    monkeypatch.setattr(verifier, 'get_machine_code_or_none', lambda: client_machine_code)
    status, k, err = verifier.verify(license_code)
    assert status == LicenseStatus.AUTHORIZED
    assert k == keys['questions_master_key']
    assert err is None

    # 5. 用 K 解密全库
    dm = DataManager(base_dir=str(tmp_path))
    full_qs = dm.load_full_questions(k)
    assert len(full_qs) == 25
    assert full_qs[0]['number'] == 1


def test_trial_loads_without_license(full_setup):
    """无授权时应能加载 trial。"""
    tmp_path = full_setup['tmp_path']
    encrypt_questions.main()

    dm = DataManager(base_dir=str(tmp_path))
    trial = dm.load_trial_questions()
    assert len(trial) == 20

    meta = dm.load_meta()
    assert meta['total'] == 25
    assert meta['trial_count'] == 20
