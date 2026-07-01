"""密码学工具模块（客户端与作者侧共享）。

集中放置 license/verifier.py 与 author_tools/generate_license.py 共用的
密码学常量与函数，防止两边实现漂移（TD-03 修复）。
"""

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# PBKDF2 迭代次数（NIST SP 800-132 推荐 ≥ 600000）
PBKDF2_ITERATIONS = 600000


def derive_dk(machine_code: str, salt: bytes) -> bytes:
    """从机器码 + salt 派生 32 字节 DK（PBKDF2-HMAC-SHA256）。

    客户端（verifier.py）与作者侧（generate_license.py）共用此函数，
    确保 DK 派生逻辑严格一致。

    Args:
        machine_code: 64 字符 hex 机器码
        salt: 16 字节随机盐

    Returns:
        32 字节派生密钥
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(machine_code.encode("utf-8"))
