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


class _SuppressTxnNoiseFilter(logging.Filter):
    """过滤掉 SQLAlchemy engine 的事务标记行（BEGIN/COMMIT/ROLLBACK/SAVEPOINT）。

    这些行与真正的 SQL 语句走同一个 logger、同为 INFO 级，echo 无法单独关闭。
    只保留有排查价值的 SQL 语句本身，事务噪音一律丢弃。
    挂在 handler 上（而非某个 logger），因为实际发日志的 logger 名带 logging_name
    后缀，挂在祖先 logger 上滤不到传播下来的记录。
    """

    _TXN_PREFIXES = (
        "BEGIN",
        "COMMIT",
        "ROLLBACK",
        "SAVEPOINT",
        "RELEASE SAVEPOINT",
    )

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name.startswith("sqlalchemy.engine"):
            msg = record.getMessage().lstrip()
            if msg.startswith(self._TXN_PREFIXES):
                return False
        return True


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
        # 注意：engine（SQL 语句）与 pool（连接池 checkout/return 等噪音）分别由
        # SQL_ECHO / SQL_ECHO_POOL 控制，不再跟随 LOG_LEVEL。否则应用一开 DEBUG，
        # 就会被 SQLAlchemy 刷爆（常驻进程如 CALLBACK_SERVER 尤甚）。
        # 未打开的一律显式压到 WARNING，避免 LOG_LEVEL=DEBUG 时经 root logger 传播过来。
        logging.getLogger("sqlalchemy.engine").setLevel(
            logging.INFO if settings.SQL_ECHO else logging.WARNING)
        logging.getLogger("sqlalchemy.pool").setLevel(
            logging.DEBUG if settings.SQL_ECHO_POOL else logging.WARNING)

        # 开启 SQL 日志但不想看事务标记（BEGIN/COMMIT/ROLLBACK）时，给根 logger
        # 的所有 handler 挂上过滤器。SQL_ECHO_TXN=true 可保留事务标记。
        if settings.SQL_ECHO and not settings.SQL_ECHO_TXN:
            self._install_txn_noise_filter()

        # 创建数据库引擎，使用连接池
        # 注意：不用 echo/echo_pool（保持 False），SQL 日志纯靠上面的 logger 级别驱动。
        # 因为 echo=True 时 SQLAlchemy 会给引擎 logger 自加一个默认 StreamHandler，
        # 打出一份平铺格式、且绕过我们过滤器的重复日志（事务标记也会重复出现）。
        self._engine = create_engine(
            settings.DATABASE_URL,
            echo=False,
            echo_pool=False,
            poolclass=QueuePool,
            pool_size=settings.MYSQL_POOL_SIZE,
            max_overflow=settings.MYSQL_MAX_OVERFLOW,
            pool_timeout=settings.MYSQL_POOL_TIMEOUT,
            pool_recycle=settings.MYSQL_POOL_RECYCLE,
            logging_name="sqlalchemy.engine",
        )

        # 摘掉 SQLAlchemy 可能为引擎/连接池 logger 自加的默认 handler：一旦检测到
        # 会输出 INFO/DEBUG，它会补一个 StreamHandler，绕过我们的格式与事务过滤器。
        # 清空后这些记录只向上传播到 root handler，格式统一、过滤器生效。
        for _lg in (getattr(self._engine, "logger", None),
                    getattr(self._engine.pool, "logger", None)):
            if isinstance(_lg, logging.Logger):
                _lg.handlers = []
                _lg.propagate = True

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

    @staticmethod
    def _install_txn_noise_filter():
        """把事务噪音过滤器挂到根 logger 的每个 handler 上（幂等）。"""
        root = logging.getLogger()
        for handler in root.handlers:
            if not any(isinstance(f, _SuppressTxnNoiseFilter)
                       for f in handler.filters):
                handler.addFilter(_SuppressTxnNoiseFilter())

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
