from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from typing import Generator
import logging
from schedule_core.config.settings import core_settings as settings

# 配置 SQLAlchemy 日志
if settings.LOG_LEVEL.upper() == "DEBUG":
    logging.basicConfig()
    logging.getLogger("sqlalchemy.engine").setLevel(logging.DEBUG)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.DEBUG)

# 创建数据库引擎
engine = create_engine(
    settings.DATABASE_URL,
    echo=True if settings.LOG_LEVEL.upper() == "DEBUG" else False,
    logging_name="sqlalchemy.engine",
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基类
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
