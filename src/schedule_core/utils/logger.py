"""
Logging utility for applications.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from schedule_core.config.settings import core_settings as settings


def get_logger(name="schedule_core", log_file=None):
    """
    获取配置好的日志记录器

    Args:
        name: 日志记录器名称
        log_file: 日志文件名，默认为None，此时使用name.log

    Returns:
        配置好的日志记录器
    """
    # 确保日志目录存在
    settings.LOG_DIR.mkdir(parents=True, exist_ok=True)

    # 配置日志
    logger = logging.getLogger(name)
    logger.setLevel(settings.LOG_LEVEL)

    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(settings.LOG_LEVEL)

    # 创建文件处理器
    if log_file is None:
        log_file = f"{name}.log"

    # 使用 RotatingFileHandler 替代 FileHandler
    file_handler = RotatingFileHandler(
        filename=settings.LOG_DIR / log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8")
    file_handler.setLevel(settings.LOG_LEVEL)

    # 创建格式化器，使用更详细的日志格式
    formatter = logging.Formatter(
        fmt=settings.LOG_FORMAT, datefmt=settings.LOG_DATE_FORMAT)
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    # 清除已有的处理器，防止重复添加
    if logger.handlers:
        logger.handlers = []

    # 添加处理器到日志记录器
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    # 设置 propagate 为 False，防止日志向上传播
    logger.propagate = False

    # 确保根日志记录器也使用相同的格式
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)
        root_logger.setLevel(settings.LOG_LEVEL)

    return logger


# 默认日志记录器
logger = get_logger()
