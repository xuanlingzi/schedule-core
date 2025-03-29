"""
Schedule Core - 核心功能模块包
"""

__version__ = "0.1.0"

from schedule_core.core.scheduler import TaskScheduler
from schedule_core.utils.logger import logger, get_logger
from schedule_core.config.settings import core_settings
from schedule_core.connections.database import db_manager
from schedule_core.connections.redis import redis_manager
from schedule_core.connections.mq import mq_manager

__all__ = [
    "TaskScheduler",
    "logger",
    "get_logger",
    "core_settings",
    "db_manager",
    "redis_manager",
    "mq_manager",
]
