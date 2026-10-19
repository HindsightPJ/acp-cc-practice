"""领域模型（P1）：为题目数据提供类型安全的封装。

核心目标：
- 替代项目内大量使用的 Dict[str, Any]，让题目字段在静态检查阶段可见；
- 提供 from_dict 以便与 JSON/加密题库无缝转换；
- 保持与现有 UI 逻辑的兼容（如 options 列表、answer 字符串等）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Option:
    """单个选项。"""

    letter: str
    text: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Option":
        return cls(
            letter=str(data.get("letter", "")).upper(),
            text=str(data.get("text", "")),
        )


@dataclass
class Question:
    """题目模型。"""

    number: int
    content: str
    options: list[Option] = field(default_factory=list)
    answer: str = ""
    type: str = "single"  # "single" or "multiple"
    explanation: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Question":
        raw_options = data.get("options", []) or []
        # 非法结构必须显式失败：静默替换为空选项会留下"题目在但不可作答"的
        # 僵尸题且无任何提示（fail-open）；由 DataManager 转 DataLoadError 友好文案
        if not isinstance(raw_options, list):
            raise ValueError("options 必须为数组")
        options = [
            Option.from_dict(opt) if isinstance(opt, dict) else Option("", "")
            for opt in raw_options
        ]
        answer = str(data.get("answer", "") or "").upper()
        q_type = data.get("type", "single")
        if q_type not in ("single", "multiple"):
            q_type = "multiple" if len(answer) > 1 else "single"
        return cls(
            number=int(data.get("number", 0)),
            content=str(data.get("content", "")),
            options=options,
            answer=answer,
            type=q_type,
            explanation=str(data.get("explanation", "")),
        )
