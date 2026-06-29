"""data_manager.py 单元测试。"""
import json
import os
import sys
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from data_manager import DataManager  # pylint: disable=wrong-import-position


@pytest.fixture
def setup_data_dir(tmp_path):
    """搭建 data 目录。"""
    data_dir = tmp_path / 'data'
    data_dir.mkdir()
    return tmp_path, data_dir


def make_questions(count):
    return [
        {
            'number': i,
            'content': f'题 {i}',
            'options': [{'letter': 'A', 'text': 'a'}, {'letter': 'B', 'text': 'b'}],
            'answer': 'A',
            'type': 'single',
            'explanation': '',
        }
        for i in range(1, count + 1)
    ]


def write_meta(data_dir, total, trial_count=20):
    (data_dir / 'questions_meta.json').write_text(
        json.dumps({'total': total, 'trial_count': trial_count, 'version': '1.0'}),
        encoding='utf-8',
    )


def write_trial(data_dir, questions):
    (data_dir / 'questions_trial.json').write_text(
        json.dumps(questions, ensure_ascii=False), encoding='utf-8',
    )


def write_enc(data_dir, questions, key):
    f = Fernet(key.encode())
    plaintext = json.dumps(questions, ensure_ascii=False).encode('utf-8')
    (data_dir / 'questions.enc').write_bytes(f.encrypt(plaintext))


def test_load_meta_returns_dict(setup_data_dir):
    """load_meta 应返回元数据 dict。"""
    tmp_path, data_dir = setup_data_dir
    write_meta(data_dir, 868, 20)
    dm = DataManager(base_dir=str(tmp_path))
    meta = dm.load_meta()
    assert meta['total'] == 868
    assert meta['trial_count'] == 20


def test_load_meta_missing_returns_none(setup_data_dir):
    """meta 不存在 → None。"""
    tmp_path, _ = setup_data_dir
    dm = DataManager(base_dir=str(tmp_path))
    assert dm.load_meta() is None


def test_load_trial_questions(setup_data_dir):
    """load_trial_questions 应加载前 20 题。"""
    tmp_path, data_dir = setup_data_dir
    qs = make_questions(25)
    write_trial(data_dir, qs[:20])
    write_meta(data_dir, 25, 20)
    dm = DataManager(base_dir=str(tmp_path))
    trial = dm.load_trial_questions()
    assert len(trial) == 20
    assert trial[0]['number'] == 1


def test_load_full_questions_with_k(setup_data_dir):
    """load_full_questions 用 K 解密全库。"""
    tmp_path, data_dir = setup_data_dir
    qs = make_questions(25)
    key = Fernet.generate_key().decode()
    write_enc(data_dir, qs, key)
    write_meta(data_dir, 25, 20)
    dm = DataManager(base_dir=str(tmp_path))
    full = dm.load_full_questions(key)
    assert len(full) == 25
    assert full[24]['number'] == 25


def test_load_full_questions_wrong_k(setup_data_dir):
    """K 错误应抛 DataLoadError。"""
    tmp_path, data_dir = setup_data_dir
    qs = make_questions(25)
    real_key = Fernet.generate_key().decode()
    write_enc(data_dir, qs, real_key)
    wrong_key = Fernet.generate_key().decode()
    dm = DataManager(base_dir=str(tmp_path))
    with pytest.raises(Exception):
        dm.load_full_questions(wrong_key)
