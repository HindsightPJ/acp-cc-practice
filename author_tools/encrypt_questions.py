"""加密题库脚本：读 data/questions.json + .env 的 K，生成：
    - data/questions.enc      全库 Fernet 密文
    - data/questions_trial.json 前 20 题明文
    - data/questions_meta.json  元数据 {total, trial_count, version}

使用：
    python encrypt_questions.py

K 来自 .env 的 QUESTIONS_MASTER_KEY。K 不变时重新加密不影响已签发的注册码。
"""
from typing import List, Dict, Any, cast
import json
import os
import sys

from cryptography.fernet import Fernet

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # acp-cc-practice/
sys.path.insert(0, BASE_DIR)
from env_utils import load_env  # pylint: disable=wrong-import-position
ENV_FILE = os.path.join(BASE_DIR, '.env')
DATA_DIR = os.path.join(BASE_DIR, 'data')
QUESTIONS_JSON = os.path.join(DATA_DIR, 'questions.json')
QUESTIONS_ENC = os.path.join(DATA_DIR, 'questions.enc')
QUESTIONS_TRIAL = os.path.join(DATA_DIR, 'questions_trial.json')
QUESTIONS_META = os.path.join(DATA_DIR, 'questions_meta.json')

TRIAL_COUNT = 20
META_VERSION = "1.0"


def load_master_key() -> str:
    """从 .env 读取 QUESTIONS_MASTER_KEY（TD-05: 改用统一 load_env）。"""
    if not os.path.exists(ENV_FILE):
        print(f"[错误] 找不到 .env: {ENV_FILE}", file=sys.stderr)
        print("请先运行 keygen.py 生成密钥。", file=sys.stderr)
        sys.exit(1)
    env = load_env(ENV_FILE)
    key = env.get('QUESTIONS_MASTER_KEY')
    if not key:
        print("[错误] .env 中未找到 QUESTIONS_MASTER_KEY", file=sys.stderr)
        sys.exit(1)
    return key


def load_questions() -> List[Dict[str, Any]]:
    """读取明文题库。"""
    if not os.path.exists(QUESTIONS_JSON):
        print(f"[错误] 找不到明文题库: {QUESTIONS_JSON}", file=sys.stderr)
        sys.exit(1)
    with open(QUESTIONS_JSON, 'r', encoding='utf-8') as f:
        return cast(List[Dict[str, Any]], json.load(f))


def encrypt_and_write(questions: List[Dict[str, Any]], key: str) -> None:
    """加密全库并写入 questions.enc。"""
    fernet = Fernet(key.encode())
    plaintext = json.dumps(questions, ensure_ascii=False).encode('utf-8')
    ciphertext = fernet.encrypt(plaintext)
    with open(QUESTIONS_ENC, 'wb') as f:
        f.write(ciphertext)


def write_trial(questions: list) -> None:
    """切前 20 题写入 questions_trial.json。"""
    trial = questions[:TRIAL_COUNT]
    with open(QUESTIONS_TRIAL, 'w', encoding='utf-8') as f:
        json.dump(trial, f, ensure_ascii=False, indent=2)


def write_meta(total: int) -> None:
    """写入 questions_meta.json。"""
    meta = {
        'total': total,
        'trial_count': min(TRIAL_COUNT, total),
        'version': META_VERSION,
    }
    with open(QUESTIONS_META, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def main() -> int:
    key = load_master_key()
    questions = load_questions()

    encrypt_and_write(questions, key)
    write_trial(questions)
    write_meta(len(questions))

    print(f"[加密完成]")
    print(f"  全库密文: {QUESTIONS_ENC} ({len(questions)} 题)")
    print(f"  试用题:   {QUESTIONS_TRIAL} ({min(TRIAL_COUNT, len(questions))} 题)")
    print(f"  元数据:   {QUESTIONS_META}")
    print(f"  K 未变，已签发注册码继续有效。")
    return 0


if __name__ == '__main__':
    sys.exit(main())
