"""
连接初始化模块
用于系统启动时初始化所有连接
"""

from .database import db_manager
from .redis import redis_manager
from .mq import mq_manager
from .wechat import wechat_manager
from .smtp import smtp_manager
from .sms import sms_manager
from schedule_core.config.settings import core_settings
import logging

logger = logging.getLogger(__name__)


def init_connections():
    """初始化所有连接"""
    try:
        # 初始化数据库连接
        logger.info("正在初始化数据库连接...")
        db_manager._initialize()

        # 初始化Redis连接
        logger.info("正在初始化Redis连接...")
        redis_manager._initialize()

        # 初始化MQ连接
        logger.info("正在初始化MQ连接...")
        mq_manager._initialize()

        # 初始化微信连接
        logger.info("正在初始化微信连接...")
        wechat_manager._initialize()

        # 初始化SMTP连接
        logger.info("正在初始化SMTP连接...")
        smtp_manager._initialize()

        # 初始化短信连接
        logger.info("正在初始化短信连接...")
        sms_manager._initialize()

        logger.info("所有连接初始化完成")
    except Exception as e:
        logger.error("连接初始化失败: %s", str(e))
        raise
