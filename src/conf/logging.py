"""Loguru 日志配置模块。"""

import sys
from functools import cache
from pathlib import Path

from loguru import logger

from conf import config

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_LOG_DIR = _PROJECT_ROOT / "logs"


@cache
def must_init() -> None:
    """初始化日志配置，只执行一次。"""
    _LOG_DIR.mkdir(exist_ok=True)

    # 移除默认 handler
    logger.remove()

    # 控制台输出
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="DEBUG" if config.DEBUG else "INFO",
        colorize=True,
    )

    # 文件输出
    logger.add(
        _LOG_DIR / "backend.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG" if config.DEBUG else "INFO",
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        encoding="utf-8",
    )
