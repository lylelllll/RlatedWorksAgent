"""Loguru 日志配置模块。"""

import sys
from loguru import logger


def setup_logging(log_level: str = "INFO", log_file: str | None = None) -> None:
    """配置 loguru 日志。"""
    logger.remove()  # 移除默认处理器

    # 控制台输出（彩色）
    fmt = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    logger.add(sys.stderr, format=fmt, level=log_level, colorize=True)

    # 文件输出（可选）
    if log_file:
        logger.add(
            log_file,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level="DEBUG",
            rotation="10 MB",
            retention="7 days",
        )
