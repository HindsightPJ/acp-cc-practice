"""license_dialog.py 单元测试。

覆盖：
- _get_license_error_message: 错误码 → 用户可读消息
- _verify_and_save_license: 生产路径全链路（显式 machine_code → 验证 → 落盘）
- LicenseDialog 对话框流：输入 → 验证 → 轮询回调 → accept 关闭
"""

from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from PySide6.QtWidgets import QDialog

from ui.license_dialog import (
    LicenseDialog,
    _get_license_error_message,
    _verify_and_save_license,
    _LICENSE_ERROR_MESSAGES,
)
from license import LicenseStatus, LicenseError
from conftest import _make_license  # noqa: I001,E402 - pytest 路径注入使然


# ---------- _get_license_error_message 测试 ----------


def test_error_message_none():
    """err=None 时返回默认失败消息。"""
    assert _get_license_error_message(None) == "授权失败，请检查注册码。"


def test_error_message_invalid_signature():
    """INVALID_SIGNATURE 错误。"""
    assert _get_license_error_message(LicenseError.INVALID_SIGNATURE) == "注册码无效，请联系作者。"


def test_error_message_wrong_machine():
    """WRONG_MACHINE 错误。"""
    assert (
        _get_license_error_message(LicenseError.WRONG_MACHINE)
        == "注册码不属于本机，请确认机器码后重新申请。"
    )


def test_error_message_corrupt_questions():
    """CORRUPT_QUESTIONS 错误。"""
    assert (
        _get_license_error_message(LicenseError.CORRUPT_QUESTIONS) == "题库密文损坏，请联系作者。"
    )


def test_error_message_corrupt_license():
    """CORRUPT_LICENSE_FILE 错误。"""
    assert _get_license_error_message(LicenseError.CORRUPT_LICENSE_FILE) == "注册码文件损坏。"


def test_error_message_unknown():
    """未知错误码返回兜底消息。"""
    fake_err = MagicMock()
    fake_err.value = "unknown_error"
    assert _get_license_error_message(fake_err) == "授权失败。"


def test_error_message_dict_keys_complete():
    """错误消息字典应覆盖所有 LicenseError 枚举值 + None。"""
    expected_keys = {None} | {e.value for e in LicenseError}
    assert set(_LICENSE_ERROR_MESSAGES.keys()) == expected_keys


# ---------- _verify_and_save_license 测试 ----------


def test_verify_and_save_success():
    """验证成功且保存成功 → (True, 成功消息, True)。"""
    with patch("ui.license_dialog.verify", return_value=(LicenseStatus.AUTHORIZED, "K123", None)):
        mock_verifier = MagicMock()
        mock_verifier.save_license.return_value = True
        with patch("ui.license_dialog.LicenseVerifier", return_value=mock_verifier):
            success, msg, should_close = _verify_and_save_license("valid-code", "/tmp/data")
    assert success is True
    assert "授权成功" in msg
    assert should_close is True
    mock_verifier.save_license.assert_called_once_with("valid-code")


def test_verify_and_save_save_fails():
    """验证成功但保存失败 → (False, 失败消息, False)。"""
    with patch("ui.license_dialog.verify", return_value=(LicenseStatus.AUTHORIZED, "K123", None)):
        mock_verifier = MagicMock()
        mock_verifier.save_license.return_value = False
        with patch("ui.license_dialog.LicenseVerifier", return_value=mock_verifier):
            success, msg, should_close = _verify_and_save_license("valid-code", "/tmp/data")
    assert success is False
    assert "保存到本地失败" in msg
    assert should_close is False


def test_verify_and_save_invalid_code():
    """验证失败（无效签名）→ (False, 错误消息, False)。"""
    with patch(
        "ui.license_dialog.verify",
        return_value=(LicenseStatus.TRIAL, None, LicenseError.INVALID_SIGNATURE),
    ):
        success, msg, should_close = _verify_and_save_license("bad-code", "/tmp/data")
    assert success is False
    assert "注册码无效" in msg
    assert should_close is False


def test_verify_and_save_wrong_machine():
    """验证失败（机器码不匹配）→ (False, 错误消息, False)。"""
    with patch(
        "ui.license_dialog.verify",
        return_value=(LicenseStatus.TRIAL, None, LicenseError.WRONG_MACHINE),
    ):
        success, msg, should_close = _verify_and_save_license("code", "/tmp/data")
    assert success is False
    assert "不属于本机" in msg
    assert should_close is False


def test_verify_and_save_no_key_authorized():
    """验证状态 AUTHORIZED 但 k 为 None → 视为失败。"""
    with patch("ui.license_dialog.verify", return_value=(LicenseStatus.AUTHORIZED, None, None)):
        success, msg, should_close = _verify_and_save_license("code", "/tmp/data")
    assert success is False
    assert should_close is False


# ---------- M13: 生产路径全链路（真实密码学链 + 显式 machine_code） ----------
# 此前的测试全部 mock 掉 verify，且从不传 machine_code——生产路径
# _verify_and_save_license(code, dir, machine_code) 的复用分支从未被执行。


def test_verify_and_save_full_chain_authorized(tmp_path, patch_public_key, setup_keys):
    """真实签名注册码 + 显式 machine_code → 验证通过并落盘 license.dat。"""
    code = _make_license("a" * 64, setup_keys["k"], setup_keys["private_hex"])

    ok, msg, close = _verify_and_save_license(code, str(tmp_path), machine_code="a" * 64)

    assert ok is True
    assert close is True
    assert "授权成功" in msg
    assert (tmp_path / "license.dat").read_text(encoding="utf-8") == code


def test_verify_and_save_full_chain_wrong_machine(tmp_path, patch_public_key, setup_keys):
    """真实签名注册码 + 错误 machine_code → WRONG_MACHINE，不落盘。"""
    code = _make_license("a" * 64, setup_keys["k"], setup_keys["private_hex"])

    ok, msg, close = _verify_and_save_license(code, str(tmp_path), machine_code="b" * 64)

    assert ok is False
    assert close is False
    assert "不属于本机" in msg
    assert not (tmp_path / "license.dat").exists()


def test_verify_and_save_full_chain_save_failure(
    tmp_path, patch_public_key, setup_keys, monkeypatch
):
    """真实验证成功但落盘失败 → 明确提示写权限问题。"""
    from license.verifier import LicenseVerifier

    code = _make_license("a" * 64, setup_keys["k"], setup_keys["private_hex"])
    monkeypatch.setattr(LicenseVerifier, "save_license", lambda self, code: False)

    ok, msg, close = _verify_and_save_license(code, str(tmp_path), machine_code="a" * 64)

    assert ok is False
    assert close is False
    assert "保存到本地失败" in msg


# ---------- M13: 对话框流（输入 → 验证 → 轮询回调 → accept） ----------


def _make_dialog(qtbot, tmp_path, verify_and_save):
    dlg = LicenseDialog(None, str(tmp_path), "a" * 64, verify_and_save=verify_and_save)
    qtbot.addWidget(dlg)
    return dlg


def test_dialog_full_flow_accepts(qtbot, tmp_path, monkeypatch):
    """验证成功 → 轮询取回结果 → 弹成功框 → accept 关闭（返回 Accepted）。"""
    calls: list[str] = []

    def fake_verify(code, license_dir, machine_code):
        calls.append(code)
        return (True, "授权成功！请重启程序加载完整题库。", True)

    dlg = _make_dialog(qtbot, tmp_path, fake_verify)
    dlg._license_entry.setPlainText("TEST-CODE")

    # worker 线程同步化：start() 即执行 target，结果确定入队，消除轮询竞态
    monkeypatch.setattr(
        "ui.license_dialog.threading.Thread",
        lambda target, daemon, name: SimpleNamespace(start=lambda: target()),
    )
    dlg._on_verify()
    dlg._poll_verify_result()

    assert calls == ["TEST-CODE"]
    assert dlg.result() == QDialog.DialogCode.Accepted


def test_dialog_full_flow_reject_keeps_open(qtbot, tmp_path, monkeypatch):
    """验证失败 → 弹失败框、按钮恢复、对话框不关闭。"""
    dlg = _make_dialog(
        qtbot, tmp_path, lambda code, d, m: (False, "注册码无效，请联系作者。", False)
    )
    dlg._license_entry.setPlainText("BAD-CODE")
    monkeypatch.setattr(
        "ui.license_dialog.threading.Thread",
        lambda target, daemon, name: SimpleNamespace(start=lambda: target()),
    )

    dlg._on_verify()
    dlg._poll_verify_result()

    assert dlg._verify_btn.isEnabled() is True
    assert dlg.result() != QDialog.DialogCode.Accepted


def test_dialog_empty_input_warns_without_thread(qtbot, tmp_path, monkeypatch):
    """空输入 → warning 弹窗、不启动验证线程。"""
    thread_calls: list[object] = []
    monkeypatch.setattr(
        "ui.license_dialog.threading.Thread",
        lambda target, daemon, name: (
            thread_calls.append(target) or SimpleNamespace(start=lambda: None)
        ),
    )
    dlg = _make_dialog(qtbot, tmp_path, lambda code, d, m: (True, "", True))

    dlg._on_verify()

    assert thread_calls == []
    assert dlg.result() != QDialog.DialogCode.Accepted
