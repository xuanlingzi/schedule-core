"""
Core settings and configuration.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from urllib.parse import quote_plus
from typing import Optional

# 项目根目录
BASE_DIR = Path(__file__).parent.parent


class CoreSettings(BaseSettings):
    """核心配置类"""
    # 日志配置
    LOG_DIR: Path = Path("schedule_core")
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s"
    LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"

    # 日志切分配置
    LOG_ROTATE_BY_TIME: bool = True  # 是否按时间切分，False则按大小切分
    LOG_ROTATE_INTERVAL: str = "D"  # 切分时间单位: D=天, H=小时, M=分钟, S=秒
    LOG_ROTATE_SUFFIX: str = "%Y-%m-%d"  # 日志文件后缀格式
    LOG_MAX_BYTES: int = 10 * 1024 * 1024  # 10MB，按大小切分时使用
    LOG_BACKUP_COUNT: int = 30  # 保留的备份文件数量

    # 数据库配置
    MYSQL_USER: str = ""
    MYSQL_PASSWORD: str = ""
    MYSQL_HOST: str = ""
    MYSQL_PORT: int = 3306
    MYSQL_DATABASE: str = ""
    MYSQL_CHARSET: str = "utf8mb4"
    MYSQL_POOL_SIZE: int = 5
    MYSQL_MAX_OVERFLOW: int = 10
    MYSQL_POOL_TIMEOUT: int = 30
    MYSQL_POOL_RECYCLE: int = 1800

    # 使用 property 装饰器来动态构建 DATABASE_URL
    @property
    def DATABASE_URL(self) -> str:
        return (f"mysql+pymysql://"
                f"{self.MYSQL_USER}:"
                f"{quote_plus(self.MYSQL_PASSWORD)}@"
                f"{self.MYSQL_HOST}:"
                f"{self.MYSQL_PORT}/"
                f"{self.MYSQL_DATABASE}"
                f"?charset={self.MYSQL_CHARSET}")

    # Redis配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_MAX_CONNECTIONS: int = 10
    REDIS_SOCKET_TIMEOUT: int = 5
    REDIS_SOCKET_CONNECT_TIMEOUT: int = 5

    # RabbitMQ配置
    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_VHOST: str = "/"
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASSWORD: str = "guest"
    RABBITMQ_HEARTBEAT: int = 600
    RABBITMQ_BLOCKED_CONNECTION_TIMEOUT: int = 300

    # 微信配置
    WECHAT_APP_ID: str = ""
    WECHAT_APP_SECRET: str = ""
    WECHAT_CALLBACK_ADDR: str = ""
    WECHAT_SCOPE: str = "snsapi_userinfo"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "allow",
        "case_sensitive": True  # 确保大小写敏感
    }


# 创建全局设置实例
core_settings = CoreSettings()
