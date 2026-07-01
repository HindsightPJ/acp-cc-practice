"""极简国际化支持（TD-34）。

当前仅内置中文（zh）与英文（en）两套字符串。用法：

    from .i18n import _
    label = tk.Label(parent, text=_("练习"))

语言切换通过 set_language(code) 完成；切换后新创建的 UI 组件会使用新语言。
"""

from typing import Dict

_DEFAULT_LANG = "zh"
_CURRENT_LANG = _DEFAULT_LANG

_STRINGS: Dict[str, Dict[str, str]] = {
    "zh": {
        # 通用
        "app_title": "ACP 云计算练习",
        "ok": "确定",
        "cancel": "取消",
        "yes": "是",
        "no": "否",
        "submit": "提交答案",
        "next": "下一题",
        "prev": "上一题",
        "show_explanation": "查看解析",
        "start": "开始",
        "restart": "重新开始",
        # 模式
        "mode_practice": "练习",
        "mode_exam": "考试",
        "mode_review": "背题",
        "mode_wrong": "错题本",
        # Header / Sidebar
        "total_questions": "题库共 {total} 题",
        "trial_only": "试用版 {trial} 题",
        "authorized": "已授权完整题库",
        "authorized_status": "已授权",
        "trial_status": "试用版（前 {trial} 题）",
        "practiced": "已练 {count} 题",
        "accuracy": "正确率 {accuracy}%",
        "wrong_count": "错题 {count}",
        "input_license": "输入注册码",
        "mastery": "就绪度",
        "all_wrong": "全部错题",
        "settings": "设置",
        "language": "语言",
        "dark_mode": "暗色模式",
        "restart_to_apply": "设置已保存，重启后生效。",
        # Practice
        "practice_title": "练习模式",
        "practice_submit_hint": "选择答案后点击提交",
        "correct": "回答正确",
        "wrong": "回答错误",
        "correct_answer": "正确答案：{answer}",
        "your_answer": "你的答案：{answer}",
        "explanation": "解析",
        "no_explanation": "暂无解析",
        # Exam
        "exam_title": "考试模式",
        "exam_remaining": "剩余 {count} 题",
        "exam_time_left": "剩余 {minutes:02d}:{seconds:02d}",
        "exam_finish_confirm": "确定交卷？",
        "exam_report_title": "考试成绩",
        "exam_report_score": "得分：{score}",
        "exam_report_time": "用时：{time}",
        "exam_report_accuracy": "正确率：{accuracy}%",
        # Review
        "review_title": "背题模式",
        "review_reveal": "显示答案",
        # Wrong book
        "wrong_book_title": "错题本",
        "wrong_book_empty": "暂无错题，继续练习吧！",
        "wrong_book_practice": "练习错题",
        "wrong_book_clear": "清空错题",
        "wrong_book_clear_confirm": "确定清空所有错题？此操作不可撤销。",
        "wrong_book_result_title": "错题练习完成",
        "wrong_book_result_msg": "本次答对 {correct} 题，答错 {wrong} 题。是否移除已掌握的错题？",
        "mastered": "已掌握",
        # License
        "license_title": "输入注册码",
        "machine_code": "机器码：{code}",
        "license_placeholder": "在此粘贴注册码...",
        "verify": "验证",
        "license_success": "授权成功！请重启程序加载完整题库。",
        "license_save_failed": "注册码验证成功，但保存到本地失败。\n请检查程序目录写入权限。",
        "license_failed": "授权失败，请检查注册码。",
        "license_invalid": "注册码无效，请联系作者。",
        "license_wrong_machine": "注册码不属于本机，请确认机器码后重新申请。",
        "license_corrupt_questions": "题库密文损坏，请联系作者。",
        "license_corrupt_license": "注册码文件损坏。",
        "machine_code_error": "无法读取本机机器码，授权仅支持 Windows。",
        "license_verify_error": "验证出错：{error}",
        # Main errors
        "error": "错误",
        "fatal_trial_missing": "试用题库缺失，请重新下载程序。",
        "fatal_load_failed": "题库数据加载失败:\n\n{error}",
        "fatal_no_questions": "未能解析出任何题目！",
        "startup_error": "启动错误",
        "license_warning": "授权提示",
        "license_warning_msg": "本地注册码验证失败，已降级试用模式。\n请重新输入注册码。",
    },
    "en": {
        "app_title": "ACP Cloud Computing Practice",
        "ok": "OK",
        "cancel": "Cancel",
        "yes": "Yes",
        "no": "No",
        "submit": "Submit",
        "next": "Next",
        "prev": "Previous",
        "show_explanation": "Explanation",
        "start": "Start",
        "restart": "Restart",
        "mode_practice": "Practice",
        "mode_exam": "Exam",
        "mode_review": "Review",
        "mode_wrong": "Wrong Book",
        "total_questions": "Total {total} questions",
        "trial_only": "Trial {trial} questions",
        "authorized": "Full question bank authorized",
        "authorized_status": "Authorized",
        "trial_status": "Trial (first {trial} questions)",
        "practiced": "Practiced {count}",
        "accuracy": "Accuracy {accuracy}%",
        "wrong_count": "Wrong {count}",
        "input_license": "Enter License",
        "mastery": "Readiness",
        "all_wrong": "All Wrong",
        "settings": "Settings",
        "language": "Language",
        "dark_mode": "Dark Mode",
        "restart_to_apply": "Settings saved. Restart to apply.",
        "practice_title": "Practice Mode",
        "practice_submit_hint": "Select an answer and submit",
        "correct": "Correct",
        "wrong": "Wrong",
        "correct_answer": "Correct: {answer}",
        "your_answer": "Your answer: {answer}",
        "explanation": "Explanation",
        "no_explanation": "No explanation",
        "exam_title": "Exam Mode",
        "exam_remaining": "{count} remaining",
        "exam_time_left": "{minutes:02d}:{seconds:02d} left",
        "exam_finish_confirm": "Submit exam?",
        "exam_report_title": "Exam Report",
        "exam_report_score": "Score: {score}",
        "exam_report_time": "Time: {time}",
        "exam_report_accuracy": "Accuracy: {accuracy}%",
        "review_title": "Review Mode",
        "review_reveal": "Show Answer",
        "wrong_book_title": "Wrong Book",
        "wrong_book_empty": "No wrong questions yet. Keep practicing!",
        "wrong_book_practice": "Practice Wrong",
        "wrong_book_clear": "Clear All",
        "wrong_book_clear_confirm": "Clear all wrong questions? This cannot be undone.",
        "wrong_book_result_title": "Wrong Book Practice Done",
        "wrong_book_result_msg": "Correct {correct}, wrong {wrong} this time. Remove mastered questions?",
        "mastered": "Mastered",
        "license_title": "Enter License",
        "machine_code": "Machine Code: {code}",
        "license_placeholder": "Paste license code here...",
        "verify": "Verify",
        "license_success": "Authorized! Please restart to load the full question bank.",
        "license_save_failed": "License valid, but failed to save locally.\nCheck write permissions.",
        "license_failed": "Authorization failed. Please check the license code.",
        "license_invalid": "Invalid license code. Please contact the author.",
        "license_wrong_machine": "License does not belong to this machine.",
        "license_corrupt_questions": "Question bank corrupted. Please contact the author.",
        "license_corrupt_license": "License file corrupted.",
        "machine_code_error": "Cannot read machine code. Licensing only supports Windows.",
        "license_verify_error": "Verification error: {error}",
        "error": "Error",
        "fatal_trial_missing": "Trial questions missing. Please re-download the program.",
        "fatal_load_failed": "Failed to load questions:\n\n{error}",
        "fatal_no_questions": "No questions parsed!",
        "startup_error": "Startup Error",
        "license_warning": "License",
        "license_warning_msg": "Local license verification failed, downgraded to trial mode.\nPlease re-enter license code.",
    },
}


def set_language(lang: str) -> None:
    """切换当前语言。"""
    global _CURRENT_LANG
    if lang in _STRINGS:
        _CURRENT_LANG = lang
    else:
        _CURRENT_LANG = _DEFAULT_LANG


def get_language() -> str:
    """返回当前语言代码。"""
    return _CURRENT_LANG


def get_supported_languages() -> list[str]:
    """返回支持的语言代码列表。"""
    return list(_STRINGS.keys())


def _(key: str, **kwargs) -> str:
    """获取 key 对应的翻译文本，并支持格式化占位符。"""
    text = _STRINGS.get(_CURRENT_LANG, _STRINGS[_DEFAULT_LANG]).get(key, key)
    if kwargs:
        return text.format(**kwargs)
    return text
