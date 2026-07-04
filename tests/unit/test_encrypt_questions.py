"""encrypt_questions.py 单元测试。"""
import json
import sys
from unittest.mock import Mock

import pytest
from cryptography.fernet import Fernet

import encrypt_questions


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


# ---------- load_master_key 边界测试 ----------


def test_load_master_key_returns_key(tmp_path, monkeypatch):
    """.env 存在且包含 QUESTIONS_MASTER_KEY 时返回该 key。"""
    key = Fernet.generate_key().decode()
    env_path = tmp_path / '.env'
    env_path.write_text(f'QUESTIONS_MASTER_KEY={key}\n', encoding='utf-8')
    monkeypatch.setattr(encrypt_questions, 'ENV_FILE', str(env_path))

    assert encrypt_questions.load_master_key() == key


def test_load_master_key_exits_when_env_missing(tmp_path, monkeypatch):
    """.env 缺失时调用 sys.exit(1)。"""
    monkeypatch.setattr(
        encrypt_questions, 'ENV_FILE', str(tmp_path / 'missing.env')
    )
    mock_exit = Mock(side_effect=SystemExit)
    monkeypatch.setattr(sys, 'exit', mock_exit)

    with pytest.raises(SystemExit):
        encrypt_questions.load_master_key()

    mock_exit.assert_called_once_with(1)


def test_load_master_key_exits_when_key_missing(tmp_path, monkeypatch):
    """.env 存在但缺少 QUESTIONS_MASTER_KEY 时调用 sys.exit(1)。"""
    env_path = tmp_path / '.env'
    env_path.write_text('OTHER=value\n', encoding='utf-8')
    monkeypatch.setattr(encrypt_questions, 'ENV_FILE', str(env_path))
    mock_exit = Mock(side_effect=SystemExit)
    monkeypatch.setattr(sys, 'exit', mock_exit)

    with pytest.raises(SystemExit):
        encrypt_questions.load_master_key()

    mock_exit.assert_called_once_with(1)


# ---------- main() 成功路径（mock 依赖） ----------


def test_main_success_with_mocked_dependencies(monkeypatch):
    """main() 成功路径：mock 所有依赖，验证调用链与返回值。"""
    fake_key = Fernet.generate_key().decode()
    fake_questions = [{'number': 1, 'content': 'test'}]

    mock_load_master_key = Mock(return_value=fake_key)
    mock_load_questions = Mock(return_value=fake_questions)
    mock_encrypt_and_write = Mock()
    mock_write_trial = Mock()
    mock_write_meta = Mock()

    monkeypatch.setattr(encrypt_questions, 'load_master_key', mock_load_master_key)
    monkeypatch.setattr(encrypt_questions, 'load_questions', mock_load_questions)
    monkeypatch.setattr(encrypt_questions, 'encrypt_and_write', mock_encrypt_and_write)
    monkeypatch.setattr(encrypt_questions, 'write_trial', mock_write_trial)
    monkeypatch.setattr(encrypt_questions, 'write_meta', mock_write_meta)

    assert encrypt_questions.main() == 0

    mock_load_master_key.assert_called_once()
    mock_load_questions.assert_called_once()
    mock_encrypt_and_write.assert_called_once_with(fake_questions, fake_key)
    mock_write_trial.assert_called_once_with(fake_questions)
    mock_write_meta.assert_called_once_with(len(fake_questions))
