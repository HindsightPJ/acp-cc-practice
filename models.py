"""领域模型（P1）：为题目数据提供类型安全的封装。

核心目标：
- 替代项目内大量使用的 Dict[str, Any]，让题目字段在静态检查阶段可见；
- 提供 from_dict / to_dict 以便与 JSON/加密题库无缝转换；
- 保持与现有 UI 逻辑的兼容（如 options 列表、answer 字符串等）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Option:
    """单个选项。"""

    letter: str
    text: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Option":
        return cls(
            letter=str(data.get("letter", "")).upper(),
            text=str(data.get("text", "")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {"letter": self.letter, "text": self.text}


@dataclass
class Question:
    """题目模型。"""

    number: int
    content: str
    options: List[Option] = field(default_factory=list)
    answer: str = ""
    type: str = "single"  # "single" or "multiple"
    explanation: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Question":
        raw_options = data.get("options", []) or []
        options = [Option.from_dict(opt) if isinstance(opt, dict) else Option("", "") for opt in raw_options]
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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "number": self.number,
            "content": self.content,
            "options": [opt.to_dict() for opt in self.options],
            "answer": self.answer,
            "type": self.type,
            "explanation": self.explanation,
        }

    @property
    def option_letters(self) -> List[str]:
        """返回所有选项字母列表。"""
        return [opt.letter for opt in self.options if opt.letter]

    def get_option_text(self, letter: str) -> str:
        """根据字母获取选项文本。"""
        for opt in self.options:
            if opt.letter == letter.upper():
                return opt.text
        return ""
