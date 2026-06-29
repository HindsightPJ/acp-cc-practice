"""题库授权与试用机制模块。"""
from enum import Enum


class LicenseStatus(Enum):
    """授权状态。"""
    TRIAL = "trial"                        # 试用模式
    AUTHORIZED = "authorized"              # 已授权
    UNSUPPORTED_PLATFORM = "unsupported"   # 非 Windows，降级试用
    FINGERPRINT_FAILED = "fp_failed"       # 指纹采集失败，降级试用


class LicenseError(Enum):
    """授权验证错误码。"""
    INVALID_SIGNATURE = "invalid_signature"        # 验签失败
    WRONG_MACHINE = "wrong_machine"                # 注册码不属于本机
    CORRUPT_QUESTIONS = "corrupt_questions"        # 题库密文损坏
    CORRUPT_LICENSE_FILE = "corrupt_license"       # license.dat 损坏
