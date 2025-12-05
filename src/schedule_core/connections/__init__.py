"""
连接管理模块，提供数据库、Redis、MQ等连接的管理
"""

from .database import DatabaseManager
from .redis import RedisManager, redis_manager
from .mq import RabbitMQManager, mq_manager
from .wechat import WeChatManager, wechat_manager
from .sms import SmsManager, sms_manager
from .smtp import SmtpManager, smtp_manager

__all__ = [
    "DatabaseManager",
    "RedisManager",
    "redis_manager",
    "RabbitMQManager",
    "mq_manager",
    "WeChatManager",
    "wechat_manager",
    "SmsManager",
    "sms_manager",
    "SmtpManager",
    "smtp_manager",
]
