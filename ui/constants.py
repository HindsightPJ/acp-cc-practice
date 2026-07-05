"""UI 层共享常量。

P1: 将散落在多个 UI 文件中的魔法数字/字符串集中管理，避免修改时遗漏。
包括：选项数量上限、选项键盘映射、题型标识、after 回调时间间隔。
"""

# 选项数量上限——题干最多 6 个选项（A-F / 1-6）
# 散落原位置：exam_panel.py / question_detail_card.py 的 range(6)、
# base_mode.py 的 "ABCDEF" / "123456" 键盘映射
MAX_OPTIONS: int = 6
OPTION_KEYS: str = "ABCDEF"[:MAX_OPTIONS]  # 选项字母键
OPTION_NUMBERS: str = "123456"[:MAX_OPTIONS]  # 选项数字键（备用键盘映射）

# 题型标识——与 models.Question.type 字段值保持一致
# 散落原位置：exam_session.py / practice_session.py / practice_panel.py / question_detail_card.py
QUESTION_TYPE_SINGLE: str = "single"
QUESTION_TYPE_MULTIPLE: str = "multiple"

# after 回调时间间隔（毫秒）
# 散落原位置：base_mode.py / review_mode.py / exam_mode.py
SAVE_DEBOUNCE_MS: int = 2000  # 防抖保存间隔
AUTO_SHOW_ANSWER_DELAY_MS: int = 100  # 复习模式自动显示答案延迟
TIMER_TICK_MS: int = 1000  # 考试计时器 tick 间隔
