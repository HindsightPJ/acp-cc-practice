"""keygen.py 单元测试。"""
import os
import sys
import tempfile
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

# 把 author_tools 加入 import 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'author_tools'))
import keygen  # pylint: disable=wrong-import-position


def test_generate_keys_returns_valid_fernet_key():
    """生成的 K 应是有效的 Fernet key。"""
    keys = keygen.generate_keys()
    f = Fernet(keys['questions_master_key'].encode())
    # 能加密解密即视为有效
    token = f.encrypt(b"test")
    assert f.decrypt(token) == b"test"


def test_generate_keys_returns_ed25519_keypair():
    """生成的 Ed25519 密钥对应能验签。"""
    keys = keygen.generate_keys()
    pub = Ed25519PublicKey.from_public_bytes(
        bytes.fromhex(keys['ed25519_public_key'])
    )
    # 用私钥签名，公钥验签
    private_bytes = bytes.fromhex(keys['ed25519_private_key'])
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    priv = Ed25519PrivateKey.from_private_bytes(private_bytes)
    sig = priv.sign(b"message")
    pub.verify(sig, b"message")  # 不抛异常即通过


def test_write_env_writes_all_keys(tmp_path):
    """write_env 应把所有密钥写入 .env 文件。"""
    keys = keygen.generate_keys()
    env_path = tmp_path / '.env'
    keygen.write_env(keys, str(env_path))
    content = env_path.read_text(encoding='utf-8')
    assert 'QUESTIONS_MASTER_KEY=' in content
    assert 'ED25519_PRIVATE_KEY=' in content
    assert 'ED25519_PUBLIC_KEY=' in content


# ---------- P1-5: sync_public_key_to_client 测试 ----------

_OLD_KEY = 'a' * 64
_NEW_KEY = 'b' * 64


def _write_public_key_file(base_dir: Path, key_hex: str) -> Path:
    """在 base_dir/license/public_key.py 写入指定公钥。"""
    license_dir = base_dir / 'license'
    license_dir.mkdir(parents=True, exist_ok=True)
    pk_file = license_dir / 'public_key.py'
    pk_file.write_text(
        f'"""public key"""\nED25519_PUBLIC_KEY_HEX = "{key_hex}"\n',
        encoding='utf-8',
    )
    return pk_file


def test_sync_public_key_when_key_changes(tmp_path):
    """新公钥与旧公钥不同时应写入新公钥。"""
    _write_public_key_file(tmp_path, _OLD_KEY)
    result = keygen.sync_public_key_to_client(_NEW_KEY, str(tmp_path))
    assert result is True
    pk_file = tmp_path / 'license' / 'public_key.py'
    content = pk_file.read_text(encoding='utf-8')
    assert _NEW_KEY in content
    assert _OLD_KEY not in content


def test_sync_public_key_when_key_same(tmp_path):
    """新公钥与旧公钥一致时应跳过写入。"""
    _write_public_key_file(tmp_path, _OLD_KEY)
    pk_file = tmp_path / 'license' / 'public_key.py'
    original_mtime = pk_file.stat().st_mtime_ns
    result = keygen.sync_public_key_to_client(_OLD_KEY, str(tmp_path))
    assert result is True
    # 文件未被修改
    assert pk_file.stat().st_mtime_ns == original_mtime


def test_sync_public_key_missing_file(tmp_path):
    """public_key.py 不存在时应返回 False 而非抛异常。"""
    result = keygen.sync_public_key_to_client(_NEW_KEY, str(tmp_path))
    assert result is False


def test_sync_public_key_no_match_pattern(tmp_path):
    """public_key.py 中未找到 ED25519_PUBLIC_KEY_HEX 定义时应返回 False。"""
    license_dir = tmp_path / 'license'
    license_dir.mkdir(parents=True, exist_ok=True)
    (license_dir / 'public_key.py').write_text(
        '"""empty"""\n# no key here\n', encoding='utf-8'
    )
    result = keygen.sync_public_key_to_client(_NEW_KEY, str(tmp_path))
    assert result is False


# ---------- P0-1: main() base_dir 路径计算回归测试 ----------

def test_main_base_dir_matches_sibling_tools():
    """P0-1 回归：main() 内的 base_dir 必须指向项目根（与 encrypt_questions.py /
    generate_license.py 一致），而非 author_tools/ 自身。

    此前 main() 只取 1 层 dirname，导致 .env 写到 author_tools/.env，
    且 sync_public_key_to_client 拿到的 base_dir 错误，
    使 license/public_key.py 永远不会被同步。
    """
    # keygen.py 位于 author_tools/ 下；项目根 = author_tools 的父目录
    keygen_file = Path(keygen.__file__).resolve()
    author_tools_dir = keygen_file.parent
    project_root = author_tools_dir.parent

    # 模拟 main() 中的路径计算：必须取 2 层 dirname 才是项目根
    computed_base = os.path.dirname(os.path.dirname(os.path.abspath(str(keygen_file))))

    assert os.path.abspath(computed_base) == os.path.abspath(str(project_root)), (
        f"main() base_dir 计算错误：\n"
        f"  computed = {computed_base}\n"
        f"  expected = {project_root}\n"
        f"  若只取 1 层 dirname 会得到 author_tools/ 自身，"
        f"导致 .env 和 license/public_key.py 都写错位置（P0-1 回归）。"
    )

    # 进一步验证：项目根下应能找到 license/public_key.py（main 同步目标）
    assert (Path(computed_base) / 'license' / 'public_key.py').exists(), (
        "项目根下找不到 license/public_key.py，sync_public_key_to_client 将无法工作"
    )
