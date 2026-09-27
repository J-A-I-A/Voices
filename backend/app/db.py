"""SQLAlchemy engine + session factory."""
from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from .config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
    connect_args={"options": "-c timezone=UTC"} if settings.database_url.startswith("postgresql") else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Convenience for the worker (which is not a FastAPI dependency).
# Must be a real context manager: the worker calls `with session_scope() as db`,
# and a bare generator raises TypeError there, which aborted every QC run.
@contextmanager
def session_scope() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

