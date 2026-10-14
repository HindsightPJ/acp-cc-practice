"""UI 层共享常量：选项数量、键盘映射、题型标识、after 回调间隔、布局度量。

仅存放跨文件共享的语义常量；单一文件使用的魔法数字就近定义。
主题相关色值/字体统一在 theme.py（单一取色源）。
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

# 主题模式标识——与 progress.json 的 theme_mode 键值一致
THEME_LIGHT: str = "light"
THEME_DARK: str = "dark"
THEME_MODES: tuple[str, ...] = (THEME_LIGHT, THEME_DARK)

# 布局度量（云霁/夜航双主题共用）
RADIUS_CARD: int = 14  # 卡片圆角
RADIUS_OPTION: int = 10  # 选项行圆角
RADIUS_BTN: int = 10  # 按钮圆角
RADIUS_CHIP: int = 6  # 芯片/小件圆角
SIDEBAR_WIDTH: int = 224  # 浮动侧栏宽度
RING_SIZE: int = 104  # 就绪度环直径
RING_THICKNESS: int = 8  # 就绪度环线宽
NAV_ITEM_HEIGHT: int = 30  # 侧栏导航 Pill 高度
CHROME_GAP: int = 16  # 侧栏与内容区的页面留白
CONTENT_PAD: int = 20  # 内容区内边距
