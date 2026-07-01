""".env 文件解析工具（TD-05 修复：统一三处 .env 解析）。

data_manager.py / author_tools/encrypt_questions.py / author_tools/generate_license.py
共用此模块，避免行为漂移（引号、注释处理不一致）。
"""

import os
from typing import Dict


def load_env(path: str) -> Dict[str, str]:
    """解析 .env 文件为 dict。

    支持的特性：
    - ``KEY=VALUE`` 格式
    - 引号包裹的值（``"xxx"`` 或 ``'xxx'`` 引号被剥离，保留内部内容含 #）
    - 行内注释（仅当无引号且 ``#`` 前有空格时才视为注释，避免 URL 误判）
    - 空行和独立注释行被忽略

    Args:
        path: .env 文件路径

    Returns:
        dict；文件不存在或读取失败时返回空 dict
    """
    if not os.path.exists(path):
        return {}
    result: Dict[str, str] = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                # 跳过空行和独立注释行
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                    # 引号包裹：剥离引号，保留内部内容（含 #）
                    value = value[1:-1]
                else:
                    # 无引号：行内注释仅当 # 前有空格时生效
                    if " #" in value:
                        value = value.split(" #", 1)[0].rstrip()
                if key:
                    result[key] = value
    except OSError:
        return {}
    return result
