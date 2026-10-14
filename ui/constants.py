"""UI 层共享常量：选项数量、键盘映射、题型标识、after 回调间隔。

仅存放跨文件共享的语义常量；单一文件使用的魔法数字就近定义。
"""

import string

# 选项数量上限——题干最多 6 个选项（A-F / 1-6）
MAX_OPTIONS: int = 6
# 选项字母键（A-F），base_mode 键盘映射与选项行生成共用
OPTION_KEYS: str = string.ascii_uppercase[:MAX_OPTIONS]
# 选项数字键（1-6，与字母键并列生效）
OPTION_NUMBERS: str = string.digits[1 : MAX_OPTIONS + 1]

# 题型标识——与 models.Question.type 字段值保持一致
QUESTION_TYPE_SINGLE: str = "single"
QUESTION_TYPE_MULTIPLE: str = "multiple"

# after 回调间隔（毫秒）
SAVE_DEBOUNCE_MS: int = 2000  # 防抖保存间隔
AUTO_SHOW_ANSWER_DELAY_MS: int = 100  # 复习模式自动显示答案延迟
TIMER_TICK_MS: int = 1000  # 考试计时器 tick 间隔
