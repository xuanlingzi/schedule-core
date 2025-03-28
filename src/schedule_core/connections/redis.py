"""
Redis连接管理器
提供Redis连接池的管理和连接获取功能
"""

from redis import Redis, ConnectionPool
from typing import Optional
from schedule_core.config.settings import core_settings as settings


class RedisManager:
    _instance: Optional["RedisManager"] = None
    _redis_client: Optional[Redis] = None
    _connection_pool: Optional[ConnectionPool] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._redis_client is None:
            self._initialize()

    def _initialize(self):
        """初始化Redis连接"""
        self._connection_pool = ConnectionPool(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            decode_responses=True,
        )

        self._redis_client = Redis(
            connection_pool=self._connection_pool,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
            socket_connect_timeout=settings.REDIS_SOCKET_CONNECT_TIMEOUT,
        )

    @property
    def client(self) -> Redis:
        """获取Redis客户端实例"""
        return self._redis_client

    def get_connection(self) -> Redis:
        """获取新的Redis连接"""
        return Redis(connection_pool=self._connection_pool)


# 创建全局Redis管理器实例
redis_manager = RedisManager()
