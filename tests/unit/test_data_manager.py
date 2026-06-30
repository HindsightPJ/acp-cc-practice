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



# ---------- parse_docx 测试（TD-02）----------

class _MockParagraph:
    """模拟 python-docx 的 Paragraph。"""
    def __init__(self, text):
        self.text = text


class _MockDocument:
    """模拟 python-docx 的 Document。"""
    def __init__(self, paragraphs_text):
        self.paragraphs = [_MockParagraph(t) for t in paragraphs_text]


def _patch_document(monkeypatch, paragraphs_text):
    """把 data_manager.Document 替换为返回 _MockDocument 的 lambda。"""
    monkeypatch.setattr('data_manager.Document', lambda path: _MockDocument(paragraphs_text))


def test_parse_single_question_complete(tmp_path, monkeypatch):
    """单选题完整解析：题号+题干+4选项+答案+解析。"""
    _patch_document(monkeypatch, [
        '1. 什么是 ACP？',
        'A. 选项A',
        'B. 选项B',
        'C. 选项C',
        'D. 选项D',
        '正确答案：A',
        '解析：ACP 是一种认证。',
    ])
    dm = DataManager(base_dir=str(tmp_path))
    questions = dm.parse_docx('fake.docx')

    assert len(questions) == 1
    q = questions[0]
    assert q['number'] == 1
    assert q['content'] == '什么是 ACP？'
    assert len(q['options']) == 4
    assert q['options'][0] == {'letter': 'A', 'text': '选项A'}
    assert q['options'][3] == {'letter': 'D', 'text': '选项D'}
    assert q['answer'] == 'A'
    assert q['type'] == 'single'
    assert q['explanation'] == 'ACP 是一种认证。'


def test_parse_multi_question(tmp_path, monkeypatch):
    """多选题答案应标记为 multiple。"""
    _patch_document(monkeypatch, [
        '1. 下列哪些是正确的？',
        'A. 选项A',
        'B. 选项B',
        'C. 选项C',
        'D. 选项D',
        '正确答案：ABC',
    ])
    dm = DataManager(base_dir=str(tmp_path))
    questions = dm.parse_docx('fake.docx')

    assert len(questions) == 1
    assert questions[0]['answer'] == 'ABC'
    assert questions[0]['type'] == 'multiple'


def test_parse_different_number_formats(tmp_path, monkeypatch):
    """支持三种题号分隔符：. 、 ．"""
    _patch_document(monkeypatch, [
        '1. 题目一',
        'A. 选项',
        '正确答案：A',
        '2、 题目二',
        'A. 选项',
        '正确答案：A',
        '3． 题目三',
        'A. 选项',
        '正确答案：A',
    ])
    dm = DataManager(base_dir=str(tmp_path))
    questions = dm.parse_docx('fake.docx')

    assert len(questions) == 3
    assert questions[0]['number'] == 1
    assert questions[1]['number'] == 2
    assert questions[2]['number'] == 3


def test_parse_different_option_formats(tmp_path, monkeypatch):
    """支持三种选项格式：A. / A、 / •A. / A.\t"""
    _patch_document(monkeypatch, [
        '1. 题目',
        'A. 选项A',
        'B、 选项B',
        '•C. 选项C',
        '正确答案：A',
    ])
    dm = DataManager(base_dir=str(tmp_path))
    questions = dm.parse_docx('fake.docx')

    assert len(questions[0]['options']) == 3
    assert questions[0]['options'][0] == {'letter': 'A', 'text': '选项A'}
    assert questions[0]['options'][1] == {'letter': 'B', 'text': '选项B'}
    assert questions[0]['options'][2] == {'letter': 'C', 'text': '选项C'}


def test_parse_content_continuation(tmp_path, monkeypatch):
    """题干在编号行之后单独出现时应作为 content。"""
    _patch_document(monkeypatch, [
        '1.',
        '这是一道题目的题干',
        'A. 选项A',
        '正确答案：A',
    ])
    dm = DataManager(base_dir=str(tmp_path))
    questions = dm.parse_docx('fake.docx')

    assert questions[0]['content'] == '这是一道题目的题干'


def test_parse_dedup_by_number(tmp_path, monkeypatch):
    """同一题号出现两次时保留后出现的版本。"""
    _patch_document(monkeypatch, [
        '1. 原始题目',
        'A. 原选项',
        '正确答案：A',
        '1. 修正题目',
        'A. 新选项',
        '正确答案：B',
    ])
    dm = DataManager(base_dir=str(tmp_path))
    questions = dm.parse_docx('fake.docx')

    assert len(questions) == 1
    assert questions[0]['content'] == '修正题目'
    assert questions[0]['answer'] == 'B'


def test_parse_skip_empty_paragraphs(tmp_path, monkeypatch):
    """空段落应被跳过。"""
    _patch_document(monkeypatch, [
        '',
        '   ',
        '1. 题目',
        '',
        'A. 选项',
        '',
        '正确答案：A',
        '',
    ])
    dm = DataManager(base_dir=str(tmp_path))
    questions = dm.parse_docx('fake.docx')

    assert len(questions) == 1
    assert questions[0]['number'] == 1


def test_parse_question_without_answer(tmp_path, monkeypatch):
    """无答案的题目应保留 answer=None。"""
    _patch_document(monkeypatch, [
        '1. 没有答案的题目',
        'A. 选项A',
        'B. 选项B',
    ])
    dm = DataManager(base_dir=str(tmp_path))
    questions = dm.parse_docx('fake.docx')

    assert len(questions) == 1
    assert questions[0]['answer'] is None
    assert questions[0]['type'] == 'single'


def test_parse_question_without_explanation(tmp_path, monkeypatch):
    """无解析的题目应保留 explanation=''。"""
    _patch_document(monkeypatch, [
        '1. 没有解析的题目',
        'A. 选项A',
        '正确答案：A',
    ])
    dm = DataManager(base_dir=str(tmp_path))
    questions = dm.parse_docx('fake.docx')

    assert questions[0]['explanation'] == ''


def test_parse_empty_doc(tmp_path, monkeypatch):
    """空文档应返回空列表。"""
    _patch_document(monkeypatch, [])
    dm = DataManager(base_dir=str(tmp_path))
    questions = dm.parse_docx('fake.docx')

    assert questions == []


def test_parse_multiple_questions(tmp_path, monkeypatch):
    """多道题目应按题号排序。"""
    _patch_document(monkeypatch, [
        '3. 第三题',
        'A. 选项',
        '正确答案：A',
        '1. 第一题',
        'A. 选项',
        '正确答案：A',
        '2. 第二题',
        'A. 选项',
        '正确答案：A',
    ])
    dm = DataManager(base_dir=str(tmp_path))
    questions = dm.parse_docx('fake.docx')

    assert len(questions) == 3
    assert [q['number'] for q in questions] == [1, 2, 3]


def test_parse_answer_without_prefix(tmp_path, monkeypatch):
    """答案行只有'答案'前缀也应识别。"""
    _patch_document(monkeypatch, [
        '1. 题目',
        'A. 选项A',
        'B. 选项B',
        '答案：B',
    ])
    dm = DataManager(base_dir=str(tmp_path))
    questions = dm.parse_docx('fake.docx')

    assert questions[0]['answer'] == 'B'


def test_parse_explanation_with_colon_variants(tmp_path, monkeypatch):
    """解析行支持全角和半角冒号。"""
    _patch_document(monkeypatch, [
        '1. 题目',
        'A. 选项A',
        '正确答案：A',
        '解析: 这是半角冒号的解析',
    ])
    dm = DataManager(base_dir=str(tmp_path))
    questions = dm.parse_docx('fake.docx')

    assert questions[0]['explanation'] == '这是半角冒号的解析'
