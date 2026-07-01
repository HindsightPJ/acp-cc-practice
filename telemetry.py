"""日志与遥测辅助模块（TD-31）。

提供结构化错误记录与事件上报封装，确保异常路径携带足够上下文，
便于后续排查与遥测分析。
"""

import logging
import traceback
from typing import Any, Dict, Optional


def _format_context(context: Optional[Dict[str, Any]]) -> str:
    """把上下文字典序列化为可读的 key=value 字符串。"""
    if not context:
        return ""
    parts = []
    for key, value in context.items():
        # 避免日志中出现过长对象
        text = repr(value)
        if len(text) > 200:
            text = text[:200] + "..."
        parts.append(f"{key}={text}")
    return " | ".join(parts)


def log_event(logger: logging.Logger, event: str, **context: Any) -> None:
    """记录一次结构化事件（非错误）。"""
    ctx = _format_context(context)
    if ctx:
        logger.info("[event=%s] %s", event, ctx)
    else:
        logger.info("[event=%s]", event)


def log_error(
    logger: logging.Logger,
    message: str,
    exc: Optional[BaseException] = None,
    **context: Any,
) -> None:
    """记录带上下文的错误日志。

    若传入异常对象，会追加异常类型与堆栈；否则仅记录 message + context。
    """
    ctx = _format_context(context)
    full_msg = f"{message} | {ctx}" if ctx else message
    if exc is not None:
        tb = traceback.format_exception_only(type(exc), exc)[-1].strip()
        full_msg = f"{full_msg} | exc={tb}"
        logger.error(full_msg, exc_info=exc)
    else:
        logger.error(full_msg)


def configure_app_logging(log_path: str, level: int = logging.WARNING) -> None:
    """统一配置应用日志：输出到轮转文件，默认 WARNING 级别。"""
    from logging.handlers import RotatingFileHandler

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    file_handler = RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    # 避免重复添加 handler（如 main 被多次 import）
    if not any(
        isinstance(h, RotatingFileHandler) and h.baseFilename == file_handler.baseFilename
        for h in root.handlers
    ):
        root.addHandler(file_handler)
