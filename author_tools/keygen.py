"""一次性生成题库主密钥 K + Ed25519 密钥对，写入 .env。

使用：
    python keygen.py

生成的 .env 包含：
    QUESTIONS_MASTER_KEY=<base64 的 32 字节 Fernet key>
    ED25519_PRIVATE_KEY=<64 字符 hex 的 Ed25519 私钥种子>
    ED25519_PUBLIC_KEY=<64 字符 hex 的 Ed25519 公钥>

注意：ED25519_PUBLIC_KEY 需要手动复制到客户端 license/public_key.py。
"""
import os
import sys

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, PrivateFormat, PublicFormat, NoEncryption
)


def generate_keys() -> dict:
    """生成 K + Ed25519 密钥对。

    Returns:
        dict 含 questions_master_key / ed25519_private_key / ed25519_public_key
    """
    # 题库主密钥 K：Fernet key（base64 编码的 32 字节）
    questions_master_key = Fernet.generate_key().decode('utf-8')

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
        'questions_master_key': questions_master_key,
        'ed25519_private_key': private_bytes.hex(),
        'ed25519_public_key': public_bytes.hex(),
    }


def write_env(keys: dict, env_path: str) -> None:
    """把密钥写入 .env 文件。"""
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(f"QUESTIONS_MASTER_KEY={keys['questions_master_key']}\n")
        f.write(f"ED25519_PRIVATE_KEY={keys['ed25519_private_key']}\n")
        f.write(f"ED25519_PUBLIC_KEY={keys['ed25519_public_key']}\n")


def main() -> int:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(base_dir, '.env')

    if os.path.exists(env_path):
        print(f"[警告] {env_path} 已存在。继续会覆盖。", file=sys.stderr)
        answer = input("继续？(y/N): ").strip().lower()
        if answer != 'y':
            print("已取消。")
            return 1

    keys = generate_keys()
    write_env(keys, env_path)

    print(f"[密钥已生成并写入 {env_path}]")
    print(f"  QUESTIONS_MASTER_KEY: {keys['questions_master_key'][:16]}...")
    print(f"  ED25519_PRIVATE_KEY:  {keys['ed25519_private_key'][:16]}...")
    print(f"  ED25519_PUBLIC_KEY:   {keys['ed25519_public_key']}")
    print()
    print("[下一步] 把 ED25519_PUBLIC_KEY 复制到 acp-cc-practice/license/public_key.py")
    return 0


if __name__ == '__main__':
    sys.exit(main())
