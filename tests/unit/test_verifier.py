"""verifier.py 单元测试。"""

import base64
import glob
import logging
import os
from unittest.mock import patch


from license import LicenseError, LicenseStatus
from license import verifier

# _make_license / setup_keys / patch_public_key 已上移 tests/unit/conftest.py
# （M13：license_dialog 全链路测试同样需要签发夹具）；pytest 收集时
# tests/unit 在 sys.path，可直接从 conftest 导入纯函数
from conftest import _make_license  # noqa: I001,E402 - pytest 路径注入使然


def test_verify_success(patch_public_key, setup_keys):
    """正确机器码 + 正确注册码 → 返回 AUTHORIZED + K。"""
    machine_code = "a" * 64
    license_code = _make_license(machine_code, setup_keys["k"], setup_keys["private_hex"])

    with patch("license.verifier.get_machine_code_or_none", return_value=machine_code):
        status, k, _ = verifier.verify(license_code)
    assert status == LicenseStatus.AUTHORIZED
    assert k == setup_keys["k"]


def test_verify_wrong_machine(patch_public_key, setup_keys):
    """注册码不属于本机 → WRONG_MACHINE。"""
    # 用机器 A 的码生成注册码
    license_code = _make_license("a" * 64, setup_keys["k"], setup_keys["private_hex"])
    # 但本机是机器 B
    with patch("license.verifier.get_machine_code_or_none", return_value="b" * 64):
        result = verifier.verify(license_code)
    assert result[0] == LicenseStatus.TRIAL
    assert result[1] is None
    assert result[2] == LicenseError.WRONG_MACHINE


def test_verify_invalid_signature(patch_public_key, setup_keys):
    """验签失败 → INVALID_SIGNATURE。

    在 raw bytes 层面翻转中段字节（保持长度不变），确定性触发签名失败。
    """
    machine_code = "a" * 64
    license_code = _make_license(machine_code, setup_keys["k"], setup_keys["private_hex"])

    # base64 解码 → 翻转 signature 的中段字节 → 重新编码
    raw = bytearray(base64.b64decode(license_code))
    raw[32] ^= 0xFF  # 翻转 signature 中段一字节
    tampered = base64.b64encode(bytes(raw)).decode("utf-8")

    with patch("license.verifier.get_machine_code_or_none", return_value=machine_code):
        result = verifier.verify(tampered)
    assert result[0] == LicenseStatus.TRIAL
    assert result[2] == LicenseError.INVALID_SIGNATURE


def test_verify_fingerprint_failed(patch_public_key, setup_keys):
    """指纹采集失败 → FINGERPRINT_FAILED。"""
    machine_code = "a" * 64
    license_code = _make_license(machine_code, setup_keys["k"], setup_keys["private_hex"])
    with patch("license.verifier.get_machine_code_or_none", return_value=None):
        result = verifier.verify(license_code)
    assert result[0] == LicenseStatus.FINGERPRINT_FAILED
    assert result[1] is None


def test_verify_corrupt_not_base64(patch_public_key):
    """非合法 base64 → CORRUPT_LICENSE_FILE。"""
    result = verifier.verify("!!!not-base64!!!")
    assert result[0] == LicenseStatus.TRIAL
    assert result[2] == LicenseError.CORRUPT_LICENSE_FILE


def test_verify_corrupt_wrong_length(patch_public_key):
    """base64 合法但长度不足 → CORRUPT_LICENSE_FILE。"""
    short = base64.b64encode(b"too short").decode("utf-8")
    result = verifier.verify(short)
    assert result[0] == LicenseStatus.TRIAL
    assert result[2] == LicenseError.CORRUPT_LICENSE_FILE


def test_verify_corrupt_non_string(patch_public_key):
    """非字符串输入 → CORRUPT_LICENSE_FILE。"""
    result = verifier.verify(None)  # type: ignore[arg-type]
    assert result[0] == LicenseStatus.TRIAL
    assert result[2] == LicenseError.CORRUPT_LICENSE_FILE


def test_check_local_license_no_file(tmp_path):
    """license.dat 不存在 → (TRIAL, None, False)。"""
    v = verifier.LicenseVerifier(data_dir=str(tmp_path))
    status, k, failed = v.check_local_license()
    assert status == LicenseStatus.TRIAL
    assert k is None
    assert failed is False


def test_check_local_license_with_valid_file(tmp_path, patch_public_key, setup_keys):
    """license.dat 存在且有效 → (AUTHORIZED, K, False)。"""
    machine_code = "a" * 64
    license_code = _make_license(machine_code, setup_keys["k"], setup_keys["private_hex"])
    (tmp_path / "license.dat").write_text(license_code, encoding="utf-8")

    v = verifier.LicenseVerifier(data_dir=str(tmp_path))
    with patch("license.verifier.get_machine_code_or_none", return_value=machine_code):
        status, k, failed = v.check_local_license()
    assert status == LicenseStatus.AUTHORIZED
    assert k == setup_keys["k"]
    assert failed is False


def test_check_local_license_with_invalid_file(tmp_path, patch_public_key):
    """license.dat 存在但损坏 → (TRIAL, None, True) — UI 应告警。"""
    (tmp_path / "license.dat").write_text("garbage-data", encoding="utf-8")
    v = verifier.LicenseVerifier(data_dir=str(tmp_path))
    status, k, failed = v.check_local_license()
    assert status == LicenseStatus.TRIAL
    assert k is None
    assert failed is True


def test_save_and_reload_license(tmp_path, patch_public_key, setup_keys):
    """save_license 写入后，check_local_license 应能读回并验证为 AUTHORIZED。"""
    machine_code = "a" * 64
    license_code = _make_license(machine_code, setup_keys["k"], setup_keys["private_hex"])

    v = verifier.LicenseVerifier(data_dir=str(tmp_path))
    assert v.save_license(license_code) is True
    assert os.path.exists(v.license_file)

    with patch("license.verifier.get_machine_code_or_none", return_value=machine_code):
        status, k, failed = v.check_local_license()
    assert status == LicenseStatus.AUTHORIZED
    assert k == setup_keys["k"]
    assert failed is False


# ---------- M19: save_license 失败/回滚路径（此前零覆盖） ----------


def test_save_license_final_write_failure_rolls_back_from_bak(tmp_path, monkeypatch):
    """M19: 最终落盘失败 → 返回 False、tmp 清理、从 .bak 回滚旧注册码。

    注册码持久化是授权链最后一环：失败即用户每次重启都要重新输码。
    """
    v = verifier.LicenseVerifier(data_dir=str(tmp_path))
    first_code = "first-license-code"
    assert v.save_license(first_code) is True

    real_replace = os.replace

    def failing_final_replace(src, dst):
        # 放行备份（license.dat → .bak），只在最终落盘（tmp → license.dat）失败
        if str(src).endswith(".tmp"):
            raise PermissionError(13, "Permission denied")
        return real_replace(src, dst)

    monkeypatch.setattr("license.verifier.os.replace", failing_final_replace)

    assert v.save_license("second-license-code") is False
    assert (tmp_path / "license.dat").read_text(encoding="utf-8") == first_code
    assert not (tmp_path / "license.dat.tmp").exists()


def test_save_license_rollback_failure_logs_error(tmp_path, monkeypatch, caplog):
    """M19: 回滚也失败（.bak → license.dat 同样不可写）→ 旧注册码可能丢失，
    必须 logger.error 留痕让用户可排查（L1：静默失败零容忍）。"""
    v = verifier.LicenseVerifier(data_dir=str(tmp_path))
    assert v.save_license("only-license-code") is True

    real_replace = os.replace

    def failing_replace(src, dst):
        # 放行备份（license.dat → .bak）；最终落盘（tmp → license.dat）与
        # 回滚（.bak → license.dat）都失败 → 旧注册码可能丢失
        src_name = os.path.basename(str(src))
        if src_name.endswith(".tmp") or src_name.endswith(".bak"):
            raise PermissionError(13, "Permission denied")
        return real_replace(src, dst)

    monkeypatch.setattr("license.verifier.os.replace", failing_replace)

    with caplog.at_level(logging.ERROR, logger="license.verifier"):
        assert v.save_license("second-license-code") is False

    assert any("回滚失败" in rec.message for rec in caplog.records)
    assert not (tmp_path / "license.dat.tmp").exists()


# ---------- M20: check_local_license 的 .corrupt 备份契约（此前零覆盖） ----------


def test_corrupt_license_file_backed_up_with_timestamp(tmp_path, patch_public_key):
    """M20: license.dat 损坏（base64 失败）→ 备份为 .corrupt-{ts}，避免反复读到坏文件。"""
    (tmp_path / "license.dat").write_text("garbage-data", encoding="utf-8")
    v = verifier.LicenseVerifier(data_dir=str(tmp_path))

    status, k, failed = v.check_local_license()

    assert status == LicenseStatus.TRIAL
    assert k is None
    assert failed is True
    assert glob.glob(str(tmp_path / "license.dat.corrupt-*"))


def test_wrong_machine_keeps_original_license_file(tmp_path, patch_public_key, setup_keys):
    """M20: WRONG_MACHINE 非损坏类失败 → 保留原文件、不生成 .corrupt 备份，
    便于用户换回原机器或重新申请时重试（与 verifier.py:145-147 注释的契约一致）。"""
    license_code = _make_license("a" * 64, setup_keys["k"], setup_keys["private_hex"])
    (tmp_path / "license.dat").write_text(license_code, encoding="utf-8")
    v = verifier.LicenseVerifier(data_dir=str(tmp_path))

    # 本机是机器 B：验签通过但 GCM tag 不匹配 → WRONG_MACHINE
    with patch("license.verifier.get_machine_code_or_none", return_value="b" * 64):
        status, k, failed = v.check_local_license()

    assert status == LicenseStatus.TRIAL
    assert k is None
    assert failed is True
    assert (tmp_path / "license.dat").read_text(encoding="utf-8") == license_code
    assert glob.glob(str(tmp_path / "license.dat.corrupt-*")) == []
