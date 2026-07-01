"""一次性生成题库主密钥 K + Ed25519 密钥对，写入 .env。

使用：
    python keygen.py

生成的 .env 包含：
    QUESTIONS_MASTER_KEY=<base64 的 32 字节 Fernet key>
    ED25519_PRIVATE_KEY=<64 字符 hex 的 Ed25519 私钥种子>
    ED25519_PUBLIC_KEY=<64 字符 hex 的 Ed25519 公钥>

P1-5: 自动同步公钥到 license/public_key.py，避免作者忘记手动复制
导致验签失败。仅当公钥变化时写入；已有相同公钥时跳过。
"""

import os
import re
import sys

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PrivateFormat,
    PublicFormat,
    NoEncryption,
)


def generate_keys() -> dict:
    """生成 K + Ed25519 密钥对。

    Returns:
        dict 含 questions_master_key / ed25519_private_key / ed25519_public_key
    """
    # 题库主密钥 K：Fernet key（base64 编码的 32 字节）
    questions_master_key = Fernet.generate_key().decode("utf-8")

    # Ed25519 密钥对
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    # 私钥：32 字节种子
    private_bytes = private_key.private_bytes(
        encoding=Encoding.Raw,
        format=PrivateFormat.Raw,
        encryption_algorithm=NoEncryption(),
    )
    # 公钥：32 字节
    public_bytes = public_key.public_bytes(
        encoding=Encoding.Raw,
        format=PublicFormat.Raw,
    )

    return {
        "questions_master_key": questions_master_key,
        "ed25519_private_key": private_bytes.hex(),
        "ed25519_public_key": public_bytes.hex(),
    }


def write_env(keys: dict, env_path: str) -> None:
    """把密钥写入 .env 文件。"""
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(f"QUESTIONS_MASTER_KEY={keys['questions_master_key']}\n")
        f.write(f"ED25519_PRIVATE_KEY={keys['ed25519_private_key']}\n")
        f.write(f"ED25519_PUBLIC_KEY={keys['ed25519_public_key']}\n")


def sync_public_key_to_client(public_key_hex: str, base_dir: str) -> bool:
    """P1-5: 自动同步 Ed25519 公钥到 license/public_key.py。

    仅当现有公钥与新公钥不同时才写入，避免无谓修改。
    使用正则替换，保留原文件结构与注释。

    Args:
        public_key_hex: 64 字符 hex 公钥
        base_dir: 项目根目录（acp-cc-practice/）

    Returns:
        True 表示已写入或已一致；False 表示同步失败（文件缺失/格式不匹配）
    """
    public_key_file = os.path.join(base_dir, "license", "public_key.py")
    if not os.path.exists(public_key_file):
        print(f"[警告] 找不到 {public_key_file}，请手动同步公钥", file=sys.stderr)
        return False

    try:
        with open(public_key_file, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError as e:
        print(f"[警告] 读取 public_key.py 失败: {e}，请手动同步公钥", file=sys.stderr)
        return False

    # 匹配 ED25519_PUBLIC_KEY_HEX = "..." 形式（支持单/双引号）
    pattern = re.compile(r'(ED25519_PUBLIC_KEY_HEX\s*=\s*)["\']([0-9a-fA-F]{64})["\']')
    match = pattern.search(content)
    if not match:
        print(
            "[警告] public_key.py 中未找到 ED25519_PUBLIC_KEY_HEX 定义，请手动同步公钥",
            file=sys.stderr,
        )
        return False

    existing_key = match.group(2)
    if existing_key.lower() == public_key_hex.lower():
        # 公钥已一致，无需修改
        return True

    # 替换为新公钥（保持双引号风格）
    new_content = pattern.sub(lambda m: f'{m.group(1)}"{public_key_hex}"', content)
    try:
        with open(public_key_file, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("[已同步] ED25519 公钥已写入 license/public_key.py")
        return True
    except OSError as e:
        print(f"[警告] 写入 public_key.py 失败: {e}，请手动同步公钥", file=sys.stderr)
        return False


def main() -> int:
    # P0-1: 必须取 2 层 dirname 才能指向项目根（acp-cc-practice/），
    # 与 encrypt_questions.py / generate_license.py 保持一致。
    # 此前只取 1 层会指向 author_tools/，导致 .env 写错位置，
    # 且 sync_public_key_to_client 的 base_dir 参数错误，
    # 使 license/public_key.py 永远不会被更新（同步函数找不到文件直接返回 False）。
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(base_dir, ".env")

    if os.path.exists(env_path):
        print(f"[警告] {env_path} 已存在。继续会覆盖。", file=sys.stderr)
        answer = input("继续？(y/N): ").strip().lower()
        if answer != "y":
            print("已取消。")
            return 1

    keys = generate_keys()
    write_env(keys, env_path)

    print(f"[密钥已生成并写入 {env_path}]")
    print(f"  QUESTIONS_MASTER_KEY: {keys['questions_master_key'][:16]}...")
    print(f"  ED25519_PRIVATE_KEY:  {keys['ed25519_private_key'][:16]}...")
    print(f"  ED25519_PUBLIC_KEY:   {keys['ed25519_public_key']}")
    print()

    # P1-5: 自动同步公钥到 license/public_key.py
    sync_public_key_to_client(keys["ed25519_public_key"], base_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
