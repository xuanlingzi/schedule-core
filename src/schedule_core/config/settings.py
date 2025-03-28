"""
Core settings and configuration.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from urllib.parse import quote_plus

# 项目根目录
BASE_DIR = Path(__file__).parent.parent


class CoreSettings(BaseSettings):
    # 日志配置
    LOG_DIR: Path = BASE_DIR / "logs"
    LOG_LEVEL: str = "INFO"

    # 数据库配置
    MYSQL_USER: str = ""
    MYSQL_PASSWORD: str = ""
    MYSQL_HOST: str = ""
    MYSQL_PORT: int = 3306
    MYSQL_DATABASE: str = ""
    MYSQL_CHARSET: str = "utf8mb4"

    # 使用 property 装饰器来动态构建 DATABASE_URL
    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+pymysql://"
            f"{self.MYSQL_USER}:"
            f"{quote_plus(self.MYSQL_PASSWORD)}@"
            f"{self.MYSQL_HOST}:"
            f"{self.MYSQL_PORT}/"
            f"{self.MYSQL_DATABASE}"
            f"?charset={self.MYSQL_CHARSET}"
        )

    # Redis配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0

    # RabbitMQ配置
    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASSWORD: str = "guest"
    RABBITMQ_VHOST: str = "/"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"
        case_sensitive = True  # 确保大小写敏感


# 创建全局设置实例
core_settings = CoreSettings()
