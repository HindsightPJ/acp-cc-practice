"""encrypt_questions.py 单元测试。"""
import json
import os
import sys
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'author_tools'))
import encrypt_questions  # pylint: disable=wrong-import-position


@pytest.fixture
def fake_questions():
    """生成 25 道假题用于测试。"""
    return [
        {
            'number': i,
            'content': f'测试题 {i}',
            'options': [{'letter': 'A', 'text': '选项A'}, {'letter': 'B', 'text': '选项B'}],
            'answer': 'A',
            'type': 'single',
            'explanation': f'解析 {i}',
        }
        for i in range(1, 26)
    ]


@pytest.fixture
def setup_workdir(tmp_path, fake_questions, monkeypatch):
    """搭建临时工作目录。"""
    # 准备 questions.json
    (tmp_path / 'data').mkdir()
    (tmp_path / 'data' / 'questions.json').write_text(
        json.dumps(fake_questions, ensure_ascii=False), encoding='utf-8'
    )
    # 准备 .env
    key = Fernet.generate_key().decode()
    (tmp_path / '.env').write_text(f'QUESTIONS_MASTER_KEY={key}\n', encoding='utf-8')

    # monkeypatch encrypt_questions 的路径常量
    monkeypatch.setattr(encrypt_questions, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(encrypt_questions, 'ENV_FILE', str(tmp_path / '.env'))
    monkeypatch.setattr(encrypt_questions, 'QUESTIONS_JSON', str(tmp_path / 'data' / 'questions.json'))
    monkeypatch.setattr(encrypt_questions, 'QUESTIONS_ENC', str(tmp_path / 'data' / 'questions.enc'))
    monkeypatch.setattr(encrypt_questions, 'QUESTIONS_TRIAL', str(tmp_path / 'data' / 'questions_trial.json'))
    monkeypatch.setattr(encrypt_questions, 'QUESTIONS_META', str(tmp_path / 'data' / 'questions_meta.json'))
    return tmp_path


def test_encrypt_generates_three_files(setup_workdir):
    """加密后应生成 enc / trial / meta 三个文件。"""
    assert encrypt_questions.main() == 0
    data_dir = setup_workdir / 'data'
    assert (data_dir / 'questions.enc').exists()
    assert (data_dir / 'questions_trial.json').exists()
    assert (data_dir / 'questions_meta.json').exists()


def test_trial_contains_first_20(setup_workdir, fake_questions):
    """trial 文件应包含前 20 题。"""
    encrypt_questions.main()
    trial = json.loads((setup_workdir / 'data' / 'questions_trial.json').read_text(encoding='utf-8'))
    assert len(trial) == 20
    assert trial[0]['number'] == 1
    assert trial[19]['number'] == 20


def test_meta_has_correct_total(setup_workdir, fake_questions):
    """meta 应记录 total=25, trial_count=20, version。"""
    encrypt_questions.main()
    meta = json.loads((setup_workdir / 'data' / 'questions_meta.json').read_text(encoding='utf-8'))
    assert meta['total'] == 25
    assert meta['trial_count'] == 20
    assert 'version' in meta


def test_enc_can_be_decrypted_with_k(setup_workdir, fake_questions):
    """enc 文件能用 K 解密还原全部 25 题。"""
    encrypt_questions.main()
    key = encrypt_questions.load_master_key()
    f = Fernet(key.encode())
    ciphertext = (setup_workdir / 'data' / 'questions.enc').read_bytes()
    plaintext = f.decrypt(ciphertext)
    questions = json.loads(plaintext.decode('utf-8'))
    assert len(questions) == 25


def test_re_encrypt_with_same_k_produces_decryptable_enc(setup_workdir):
    """K 不变时重新加密，新 enc 仍能用同一 K 解密。"""
    # 第一次加密
    encrypt_questions.main()
    key1 = encrypt_questions.load_master_key()
    enc1 = (setup_workdir / 'data' / 'questions.enc').read_bytes()

    # 第二次加密（模拟题库更新）
    encrypt_questions.main()
    key2 = encrypt_questions.load_master_key()
    enc2 = (setup_workdir / 'data' / 'questions.enc').read_bytes()

    # K 不变
    assert key1 == key2
    # enc 内容不同（Fernet 每次加密带随机 IV）
    assert enc1 != enc2
    # 但都能用同一 K 解密
    f = Fernet(key1.encode())
    assert json.loads(f.decrypt(enc1).decode('utf-8'))
    assert json.loads(f.decrypt(enc2).decode('utf-8'))
