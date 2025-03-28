"""
Schedule Core - 核心功能模块包
"""

__version__ = "0.1.0"

from schedule_core.core.database import get_db, Base, SessionLocal
from schedule_core.core.cache import cache
from schedule_core.core.scheduler import TaskScheduler
from schedule_core.utils.logger import logger, get_logger
from schedule_core.utils.rabbitmq import RabbitMQClient
from schedule_core.config.settings import core_settings

__all__ = [
    "get_db",
    "Base",
    "SessionLocal",
    "cache",
    "TaskScheduler",
    "logger",
    "get_logger",
    "RabbitMQClient",
    "core_settings",
]
