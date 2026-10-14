"""data_manager.py 单元测试。"""

import json
import os
import threading

import pytest
from cryptography.fernet import Fernet

from data_manager import DataLoadError, DataManager, DataSaveError


@pytest.fixture
def setup_data_dir(tmp_path):
    """搭建 data 目录。"""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return tmp_path, data_dir


def make_questions(count):
    return [
        {
            "number": i,
            "content": f"题 {i}",
            "options": [{"letter": "A", "text": "a"}, {"letter": "B", "text": "b"}],
            "answer": "A",
            "type": "single",
            "explanation": "",
        }
        for i in range(1, count + 1)
    ]


def write_meta(data_dir, total, trial_count=20):
    (data_dir / "questions_meta.json").write_text(
        json.dumps({"total": total, "trial_count": trial_count, "version": "1.0"}),
        encoding="utf-8",
    )


def write_trial(data_dir, questions):
    (data_dir / "questions_trial.json").write_text(
        json.dumps(questions, ensure_ascii=False),
        encoding="utf-8",
    )


def write_enc(data_dir, questions, key):
    f = Fernet(key.encode())
    plaintext = json.dumps(questions, ensure_ascii=False).encode("utf-8")
    (data_dir / "questions.enc").write_bytes(f.encrypt(plaintext))


def test_load_meta_returns_dict(setup_data_dir):
    """load_meta 应返回元数据 dict。"""
    tmp_path, data_dir = setup_data_dir
    write_meta(data_dir, 868, 20)
    dm = DataManager(base_dir=str(tmp_path))
    meta = dm.load_meta()
    assert meta["total"] == 868
    assert meta["trial_count"] == 20


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
    assert trial[0].number == 1


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
    assert full[24].number == 25


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


def test_load_trial_questions_malformed_entry_raises_data_load_error(setup_data_dir):
    """试用题库中存在格式错误的题目 dict 时应抛 DataLoadError 并包含题号。"""
    tmp_path, data_dir = setup_data_dir
    qs = make_questions(2)
    qs[1]["number"] = "not-a-number"
    write_trial(data_dir, qs)
    dm = DataManager(base_dir=str(tmp_path))
    with pytest.raises(DataLoadError) as exc_info:
        dm.load_trial_questions()
    assert "第2题解析失败" in str(exc_info.value)


def test_load_full_questions_malformed_encrypted_entry_raises_data_load_error(setup_data_dir):
    """加密全库中存在格式错误的题目 dict 时应抛 DataLoadError 并包含题号。"""
    tmp_path, data_dir = setup_data_dir
    qs = make_questions(3)
    qs[2]["number"] = "bad-number"
    key = Fernet.generate_key().decode()
    write_enc(data_dir, qs, key)
    dm = DataManager(base_dir=str(tmp_path))
    with pytest.raises(DataLoadError) as exc_info:
        dm.load_full_questions(key)
    assert "第3题解析失败" in str(exc_info.value)


def test_save_progress_thread_safety(tmp_path):
    """并发调用 save_progress 不应损坏 progress.json。"""
    user_data_dir = tmp_path / "data"
    user_data_dir.mkdir()
    dm = DataManager(base_dir=str(tmp_path))
    errors: list[Exception] = []

    def writer(start: int) -> None:
        for i in range(start, start + 50):
            try:
                dm.save_progress({"counter": i, "thread": start})
            except Exception as e:  # noqa: BLE001
                errors.append(e)

    threads = [threading.Thread(target=writer, args=(t * 100,)) for t in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    loaded = dm.load_progress()
    assert isinstance(loaded, dict)
    assert "counter" in loaded


# ---------- P2-7: load_progress 类型校验 ----------


def test_load_progress_with_non_dict_json_returns_default(tmp_path):
    """P2-7: progress.json 被篡改为 JSON 数组时应返回默认值而非崩溃。

    场景：用户或外部工具将 progress.json 内容改为 `[1, 2, 3]`，
    load_progress 应识别为损坏并返回默认 dict，避免 AppState 崩溃。
    """
    user_data_dir = tmp_path / "data"
    user_data_dir.mkdir()
    (user_data_dir / "progress.json").write_text("[1, 2, 3]", encoding="utf-8")

    dm = DataManager(base_dir=str(tmp_path))
    progress = dm.load_progress()

    # 应返回默认 dict 结构
    assert isinstance(progress, dict)
    assert "wrong_questions" in progress
    assert "practice_stats" in progress


def test_load_progress_with_string_json_returns_default(tmp_path):
    """P2-7: progress.json 为 JSON 字符串时应返回默认值。"""
    user_data_dir = tmp_path / "data"
    user_data_dir.mkdir()
    (user_data_dir / "progress.json").write_text('"corrupted"', encoding="utf-8")

    dm = DataManager(base_dir=str(tmp_path))
    progress = dm.load_progress()

    assert isinstance(progress, dict)
    assert "wrong_questions" in progress


def test_load_progress_with_valid_dict_loads_normally(tmp_path):
    """P2-7: 正常的 dict 结构 progress.json 应正常加载。"""
    user_data_dir = tmp_path / "data"
    user_data_dir.mkdir()
    valid_progress = {
        "wrong_questions": [10, 20],
        "practice_stats": {"correct": 5, "wrong": 3, "total": 8},
        "exam_history": [],
        "favorites": [10],
    }
    (user_data_dir / "progress.json").write_text(
        json.dumps(valid_progress, ensure_ascii=False), encoding="utf-8"
    )

    dm = DataManager(base_dir=str(tmp_path))
    progress = dm.load_progress()

    assert progress["wrong_questions"] == [10, 20]
    assert progress["practice_stats"]["correct"] == 5


# ---------- load_progress / save_progress 异常恢复路径 ----------


def test_load_progress_json_syntax_error_renames_corrupt_and_returns_default(tmp_path):
    """progress.json 存在 JSON 语法错误时，应重命名为 .corrupt 并返回默认进度。"""
    user_data_dir = tmp_path / "data"
    user_data_dir.mkdir()
    progress_file = user_data_dir / "progress.json"
    progress_file.write_text("{invalid json", encoding="utf-8")

    dm = DataManager(base_dir=str(tmp_path))
    progress = dm.load_progress()

    assert isinstance(progress, dict)
    assert "wrong_questions" in progress
    assert not progress_file.exists()
    assert list(user_data_dir.glob("progress.json.corrupt-*"))


def test_load_progress_missing_with_bak_loads_from_bak(tmp_path):
    """progress.json 缺失但 .bak 存在时，应从 .bak 加载。"""
    user_data_dir = tmp_path / "data"
    user_data_dir.mkdir()
    backup = {
        "wrong_questions": [1, 2, 3],
        "practice_stats": {"correct": 10, "wrong": 2, "total": 12},
        "exam_history": [],
        "favorites": [],
        "settings": {},
    }
    (user_data_dir / "progress.json.bak").write_text(
        json.dumps(backup, ensure_ascii=False), encoding="utf-8"
    )

    dm = DataManager(base_dir=str(tmp_path))
    progress = dm.load_progress()

    assert progress["wrong_questions"] == [1, 2, 3]
    assert progress["practice_stats"]["correct"] == 10


def test_load_progress_bak_corrupt_returns_default(tmp_path):
    """progress.json 缺失且 .bak 也损坏时，应返回默认进度。"""
    user_data_dir = tmp_path / "data"
    user_data_dir.mkdir()
    (user_data_dir / "progress.json.bak").write_text("{broken", encoding="utf-8")

    dm = DataManager(base_dir=str(tmp_path))
    progress = dm.load_progress()

    assert isinstance(progress, dict)
    assert "wrong_questions" in progress
    assert progress["practice_stats"] == {"correct": 0, "wrong": 0, "total": 0}


def test_load_progress_list_root_renames_corrupt_and_returns_default(tmp_path):
    """progress.json 根节点为 list 时，视为损坏并重命名，返回默认进度。"""
    user_data_dir = tmp_path / "data"
    user_data_dir.mkdir()
    progress_file = user_data_dir / "progress.json"
    progress_file.write_text("[1, 2, 3]", encoding="utf-8")

    dm = DataManager(base_dir=str(tmp_path))
    progress = dm.load_progress()

    assert isinstance(progress, dict)
    assert "wrong_questions" in progress
    assert not progress_file.exists()
    assert list(user_data_dir.glob("progress.json.corrupt-*"))


def test_save_progress_permission_error_raises_and_cleans_tmp(tmp_path, monkeypatch):
    """保存时最终 os.replace 触发 PermissionError，应抛 DataSaveError 并清理 .tmp。"""
    user_data_dir = tmp_path / "data"
    user_data_dir.mkdir()
    progress_file = user_data_dir / "progress.json"
    old_progress = {
        "wrong_questions": [1],
        "practice_stats": {"correct": 1, "wrong": 0, "total": 1},
    }
    progress_file.write_text(json.dumps(old_progress, ensure_ascii=False), encoding="utf-8")

    real_replace = os.replace

    def fake_replace(src, dst):
        if str(src).endswith(".tmp"):
            raise PermissionError(13, "Permission denied")
        return real_replace(src, dst)

    monkeypatch.setattr("data_manager.os.replace", fake_replace)

    dm = DataManager(base_dir=str(tmp_path))
    with pytest.raises(DataSaveError):
        dm.save_progress(
            {"wrong_questions": [99], "practice_stats": {"correct": 5, "wrong": 0, "total": 5}}
        )

    assert not (user_data_dir / "progress.json.tmp").exists()
    assert progress_file.exists()
    restored = json.loads(progress_file.read_text(encoding="utf-8"))
    assert restored["wrong_questions"] == [1]


def test_save_progress_failure_restores_from_bak(tmp_path, monkeypatch):
    """写入 .tmp 失败时，应利用已有 .bak 恢复 progress.json。"""
    user_data_dir = tmp_path / "data"
    user_data_dir.mkdir()
    progress_file = user_data_dir / "progress.json"
    old_progress = {
        "wrong_questions": [2],
        "practice_stats": {"correct": 2, "wrong": 0, "total": 2},
    }
    progress_file.write_text(json.dumps(old_progress, ensure_ascii=False), encoding="utf-8")

    def failing_dump(*args, **kwargs):
        raise OSError("write failed")

    monkeypatch.setattr("data_manager.json.dump", failing_dump)

    dm = DataManager(base_dir=str(tmp_path))
    with pytest.raises(DataSaveError):
        dm.save_progress(
            {"wrong_questions": [99], "practice_stats": {"correct": 5, "wrong": 0, "total": 5}}
        )

    assert not (user_data_dir / "progress.json.tmp").exists()
    assert progress_file.exists()
    restored = json.loads(progress_file.read_text(encoding="utf-8"))
    assert restored["wrong_questions"] == [2]
