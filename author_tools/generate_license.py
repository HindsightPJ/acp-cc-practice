"""注册码生成工具（作者侧）。

使用：
    python generate_license.py

流程：
    1. 提示输入被授权人的机器码（64 字符 hex）
    2. 读 .env 的 K + Ed25519 私钥
    3. 生成 salt + nonce，派生 DK，AES-GCM 加密 K
    4. Ed25519 签名 (salt || encrypted_K)
    5. base64 编码输出注册码
    6. 追加记录到 issued_licenses.json

密码学逻辑必须与 license/verifier.py 严格一致：
    encrypted_K = nonce(12) + AES-256-GCM(nonce, K, DK, aad=salt)
    DK = PBKDF2(machine_code, salt, 200000)
    注册码 = base64( signature(64) || salt(16) || encrypted_K(72) ) = 152 字节
"""
import base64
import json
import os
import sys
from datetime import datetime

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # acp-cc-practice/
sys.path.insert(0, BASE_DIR)
from license.crypto_utils import derive_dk
ENV_FILE = os.path.join(BASE_DIR, '.env')
ISSUED_LICENSES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'issued_licenses.json')

SALT_LEN = 16
NONCE_LEN = 12


def load_author_keys() -> dict:
    """从 .env 读取 K + Ed25519 私钥。"""
    if not os.path.exists(ENV_FILE):
        print(f"[错误] 找不到 .env: {ENV_FILE}", file=sys.stderr)
        print("请先运行 keygen.py。", file=sys.stderr)
        sys.exit(1)
    keys = {}
    with open(ENV_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('QUESTIONS_MASTER_KEY='):
                keys['k'] = line.split('=', 1)[1].strip()
            elif line.startswith('ED25519_PRIVATE_KEY='):
                keys['private_hex'] = line.split('=', 1)[1].strip()
    if 'k' not in keys or 'private_hex' not in keys:
        print("[错误] .env 缺少 QUESTIONS_MASTER_KEY 或 ED25519_PRIVATE_KEY", file=sys.stderr)
        sys.exit(1)
    return keys



def generate_license_for_machine_code(machine_code: str) -> str:
    """为指定机器码生成注册码。

    Args:
        machine_code: 64 字符 hex 的机器码

    Returns:
        base64 编码的注册码字符串（解码后 152 字节）
    """
    keys = load_author_keys()

    # 派生 DK
    salt = os.urandom(SALT_LEN)
    dk = derive_dk(machine_code, salt)

    # AES-GCM 加密 K（nonce=nonce, associated_data=salt）
    nonce = os.urandom(NONCE_LEN)
    aesgcm = AESGCM(dk)
    encrypted_k = nonce + aesgcm.encrypt(nonce, keys['k'].encode('utf-8'), salt)

    # Ed25519 签名 (salt || encrypted_K)
    private_bytes = bytes.fromhex(keys['private_hex'])
    priv = Ed25519PrivateKey.from_private_bytes(private_bytes)
    signature = priv.sign(salt + encrypted_k)

    # base64 编码
    return base64.b64encode(signature + salt + encrypted_k).decode('utf-8')


def record_issued(machine_code: str, note: str) -> None:
    """记录签发到 issued_licenses.json（同 machine_code 覆盖旧记录，去重）。"""
    records = []
    if os.path.exists(ISSUED_LICENSES):
        try:
            with open(ISSUED_LICENSES, 'r', encoding='utf-8') as f:
                records = json.load(f)
        except (OSError, json.JSONDecodeError):
            records = []

    # 去重：同 machine_code 覆盖旧记录
    records = [r for r in records if r.get('machine_code') != machine_code]
    records.append({
        'machine_code': machine_code,
        'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'note': note,
    })

    with open(ISSUED_LICENSES, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def main() -> int:
    print("=== 注册码生成工具 ===")
    print()
    machine_code = input("请输入被授权人的机器码（64 字符 hex）: ").strip()
    # 兼容从 GUI 复制时可能带入的空白/不可见字符
    machine_code = ''.join(c for c in machine_code if c in '0123456789abcdefABCDEF')
    if len(machine_code) != 64:
        print()
        print(f"[错误] 机器码格式不正确：应为 64 字符 hex，实际收到 {len(machine_code)} 字符。")
        print(f"       收到的内容（前 80 字符）：{machine_code[:80]}")
        print("       常见原因：从 GUI 复制时多选/少选了字符，或粘贴时混入了换行符。")
        print("       请重新从 GUI 复制完整的 64 字符机器码后再试。")
        input("按回车键退出...")
        return 1
    machine_code = machine_code.lower()

    note = input("备注（可选，如对方姓名）: ").strip()

    try:
        license_code = generate_license_for_machine_code(machine_code)
        record_issued(machine_code, note)
    except Exception as e:
        import traceback
        print()
        print("[错误] 生成注册码时发生异常：")
        traceback.print_exc()
        print()
        print(f"异常类型: {type(e).__name__}")
        print(f"异常信息: {e}")
        input("按回车键退出...")
        return 1

    print()
    print("=== 注册码已生成 ===")
    print(license_code)
    print()
    print(f"已记录到 {ISSUED_LICENSES}")
    input("按回车键退出...")
    return 0


if __name__ == '__main__':
    sys.exit(main())
