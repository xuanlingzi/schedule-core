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
    LOG_FILE: str = ""
    LOG_LEVEL: str = "INFO"
    # 注：日志格式由 loguru 后端在 logger.py 的 _LOGURU_FORMAT 固定（等价原格式），
    # 不再从这里读取 LOG_FORMAT / LOG_DATE_FORMAT。

    # 日志切分配置（loguru 后端）
    # LOG_ROTATE_MODE 显式指定切分策略，优先级高于 LOG_ROTATE_BY_TIME：
    #   "time"  —— 按时间(整点)+大小，谁先到谁切，适合常驻进程
    #   "size"  —— 仅按大小切，适合常驻进程
    #   "dated" —— 文件名内嵌日期，每天一个文件，不依赖进程存活，适合 systemd
    #              oneshot 短命任务（跑完即退，进程内轮转无法触发）
    # 留空时按 LOG_ROTATE_BY_TIME 回退到 "time"/"size"。
    LOG_ROTATE_MODE: str = ""
    LOG_ROTATE_BY_TIME: bool = True  # 是否按时间切分，False则按大小切分
    LOG_ROTATE_INTERVAL: str = "H"  # 切分时间单位: D=天, H=小时, M=分钟, S=秒
    LOG_MAX_BYTES: int = 10 * 1024 * 1024  # 10MB，按大小切分时使用
    LOG_BACKUP_COUNT: int = 30  # 保留的备份文件数量
    # 业务日志分流：逗号分隔的「模块关键字」，每个匹配的模块日志单独写 <关键字>.log，
    # 主日志文件则排除这些模块（只留框架自身与未分类）。留空 = 不分流（全部进主文件）。
    # 典型用于 callback_server 这种「一个进程内分发多个业务 handler」的场景，按调用
    # 模块名(record["name"])自动路由，业务代码无需改动。
    LOG_MODULE_ROUTES: str = ""

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
    # SQLAlchemy 日志开关，独立于 LOG_LEVEL，engine 与 pool 分开控制。
    # SQL_ECHO       —— engine 层，打出每条 SQL 语句（INFO 级），有业务排查价值。
    # SQL_ECHO_POOL  —— pool 层，连接池 checkout/return/rollback-on-return/closing
    #                   等高频日志（DEBUG 级），无业务意义，常驻进程会被刷屏，默认关。
    # 二者默认均关，即使 LOG_LEVEL=DEBUG 也不会被 SQLAlchemy 刷屏；按需单独打开。
    SQL_ECHO: bool = True
    SQL_ECHO_POOL: bool = False
    # SQL_ECHO_TXN —— 是否显示事务标记 BEGIN/COMMIT/ROLLBACK/SAVEPOINT（INFO 级）。
    # 默认关：开了 SQL_ECHO 时只留真正的 SQL 语句，滤掉这些高频无意义的事务行。
    SQL_ECHO_TXN: bool = False

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

    # SMTP配置
    SMTP_ADDR: str = ""
    SMTP_PORT: int = 465
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""

    # IMAP配置（用于定期清理服务端「已发送」文件夹，释放邮箱空间）
    # 用户名/密码留空时自动复用 SMTP_USERNAME/SMTP_PASSWORD（腾讯企业邮同账号）
    IMAP_ADDR: str = "imap.exmail.qq.com"
    IMAP_PORT: int = 993
    IMAP_USERNAME: str = ""
    IMAP_PASSWORD: str = ""
    # 「已发送」文件夹名；留空则自动探测带 \Sent 属性的文件夹（腾讯企业邮通常为 "Sent Messages"）
    IMAP_SENT_FOLDER: str = ""
    # 清理开关：默认关闭，配好凭据并确认策略后再开启（删除为不可逆操作）
    IMAP_SENT_CLEAN_ENABLED: bool = False
    # 只删该天数之前的已发送邮件
    IMAP_SENT_RETENTION_DAYS: int = 30
    # 演练模式：只统计与打印将删除的数量，不实际删除
    IMAP_SENT_CLEAN_DRY_RUN: bool = False
    # 收件箱清理（服务账号收件箱以退信/自动回复为主，定期清理释放空间）
    IMAP_INBOX_CLEAN_ENABLED: bool = False
    # 只删该天数之前的收件箱邮件
    IMAP_INBOX_RETENTION_DAYS: int = 30
    # 演练模式：只统计与打印将删除的数量，不实际删除
    IMAP_INBOX_CLEAN_DRY_RUN: bool = False

    # 短信配置
    SMS_ADDR: str = ""
    SMS_SECRET_ID: str = ""
    SMS_SECRET_KEY: str = ""
    SMS_APP_ID: str = ""
    SMS_APP_KEY: str = ""
    SMS_REGION: str = ""
    SMS_ALG: str = ""
    SMS_SIGNATURE: str = ""

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "allow",
        "case_sensitive": True  # 确保大小写敏感
    }


# 创建全局设置实例
core_settings = CoreSettings()
