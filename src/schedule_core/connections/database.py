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
        # 注意：SQLAlchemy 引擎/连接池日志由独立的 SQL_ECHO 控制，不再跟随
        # LOG_LEVEL。否则应用一开 DEBUG，engine 的每条 SQL、pool 的
        # checkout/return/close 就会把常驻进程（如 CALLBACK_SERVER）刷爆。
        if settings.SQL_ECHO:
            logging.basicConfig()
            logging.getLogger("sqlalchemy.engine").setLevel(logging.DEBUG)
            logging.getLogger("sqlalchemy.pool").setLevel(logging.DEBUG)
        else:
            # 显式压到 WARNING，避免 LOG_LEVEL=DEBUG 时经由 root logger 传播
            logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
            logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

        # 创建数据库引擎，使用连接池
        self._engine = create_engine(
            settings.DATABASE_URL,
            echo=settings.SQL_ECHO,
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

        # 创建只读会话工厂（读操作）
        # 注意：autocommit=True 在 SQLAlchemy 2.1+ 中已移除，
        # 对于只读查询使用 autocommit=False 即可（session close 时自动回滚）
        self._ReadSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self._engine)

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
