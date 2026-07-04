"""env_utils.py 单元测试。"""
from unittest.mock import patch

from env_utils import load_env


def test_load_env_missing_file_returns_empty_dict(tmp_path):
    """文件不存在时返回空 dict。"""
    missing = tmp_path / "missing.env"
    assert load_env(str(missing)) == {}


def test_load_env_basic_key_value(tmp_path):
    """基本 KEY=VALUE 解析。"""
    env_path = tmp_path / ".env"
    env_path.write_text("FOO=bar\nBAZ=qux\n", encoding="utf-8")
    assert load_env(str(env_path)) == {"FOO": "bar", "BAZ": "qux"}


def test_load_env_quoted_values_preserve_inline_hash(tmp_path):
    """引号值保留内部 #。"""
    env_path = tmp_path / ".env"
    env_path.write_text(
        'URL="http://example.com#section"\nPASS=\'secret#hash\'\n',
        encoding="utf-8",
    )
    assert load_env(str(env_path)) == {
        "URL": "http://example.com#section",
        "PASS": "secret#hash",
    }


def test_load_env_unquoted_inline_comment_stripped(tmp_path):
    """无引号且 # 前有空格时，行内注释被去除。"""
    env_path = tmp_path / ".env"
    env_path.write_text("KEY=value # comment\nNO_HASH=val#ue\n", encoding="utf-8")
    assert load_env(str(env_path)) == {"KEY": "value", "NO_HASH": "val#ue"}


def test_load_env_ignores_empty_and_comment_lines(tmp_path):
    """空行和独立注释行被忽略。"""
    env_path = tmp_path / ".env"
    env_path.write_text("\n# comment\n\nFOO=bar\n  \n", encoding="utf-8")
    assert load_env(str(env_path)) == {"FOO": "bar"}


def test_load_env_ignores_lines_without_equals(tmp_path):
    """不含 = 的行被忽略。"""
    env_path = tmp_path / ".env"
    env_path.write_text("FOO=bar\nNO_EQUALS\nKEY=value\n", encoding="utf-8")
    assert load_env(str(env_path)) == {"FOO": "bar", "KEY": "value"}


def test_load_env_oserror_returns_empty_dict(tmp_path):
    """读取触发 OSError 时返回空 dict。"""
    env_path = tmp_path / ".env"
    env_path.write_text("FOO=bar\n", encoding="utf-8")

    def raising_open(*args, **kwargs):
        raise OSError("cannot read")

    with patch("builtins.open", side_effect=raising_open):
        assert load_env(str(env_path)) == {}
