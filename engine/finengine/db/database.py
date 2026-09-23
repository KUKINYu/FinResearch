"""数据库连接与初始化（SQLite + SQLAlchemy 2.0）。"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from ..config import db_path


class Base(DeclarativeBase):
    pass


# SQLite：WAL 模式提升并发读写；check_same_thread=False 供 FastAPI 多线程使用
engine = create_engine(
    f"sqlite:///{db_path()}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


def init_db() -> None:
    """建表（M2 起步用 create_all；数据模型稳定后换 Alembic 迁移）。"""
    from . import models  # noqa: F401 确保模型注册到 Base

    Base.metadata.create_all(engine)
