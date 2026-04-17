"""
数据库连接管理器
提供数据库连接池的管理和会话获取功能
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.orm import declarative_base
from typing import Generator, Optional
import logging
from contextlib import contextmanager
from schedule_core.config.settings import core_settings as settings


class DatabaseManager:
    _instance: Optional["DatabaseManager"] = None
    _engine = None
    _SessionLocal = None
    _ReadSessionLocal = None
    _Base = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._engine is None:
            self._initialize()

    def _initialize(self):
        """初始化数据库连接"""
        # 配置 SQLAlchemy 日志
        if settings.LOG_LEVEL.upper() == "DEBUG":
            logging.basicConfig()
            logging.getLogger("sqlalchemy.engine").setLevel(logging.DEBUG)
            logging.getLogger("sqlalchemy.pool").setLevel(logging.DEBUG)

        # 创建数据库引擎，使用连接池
        self._engine = create_engine(
            settings.DATABASE_URL,
            echo=True if settings.LOG_LEVEL.upper() == "DEBUG" else False,
            poolclass=QueuePool,
            pool_size=settings.MYSQL_POOL_SIZE,
            max_overflow=settings.MYSQL_MAX_OVERFLOW,
            pool_timeout=settings.MYSQL_POOL_TIMEOUT,
            pool_recycle=settings.MYSQL_POOL_RECYCLE,
            logging_name="sqlalchemy.engine",
        )

        # 创建会话工厂（写操作，带事务）
        self._SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self._engine)

        # 创建只读会话工厂（读操作，无事务）
        self._ReadSessionLocal = sessionmaker(
            autocommit=True, autoflush=False, bind=self._engine)

        # 创建基类
        self._Base = declarative_base()

    @property
    def engine(self):
        return self._engine

    @property
    def Base(self):
        return self._Base

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """获取数据库会话的上下文管理器"""
        session = self._SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @contextmanager
    def get_read_session(self) -> Generator[Session, None, None]:
        """获取只读数据库会话的上下文管理器（不开启事务，避免长事务报警）

        使用 autocommit=True 的会话工厂，仅用于 SELECT 查询。
        """
        session = self._ReadSessionLocal()
        try:
            yield session
        finally:
            session.close()

    def get_db(self) -> Generator[Session, None, None]:
        """获取数据库会话的生成器函数"""
        db = self._SessionLocal()
        try:
            yield db
        finally:
            db.close()


# 创建全局数据库管理器实例
db_manager = DatabaseManager()
