import logging
from typing import Generator
from sqlmodel import SQLModel, create_engine, Session
from app.config import settings

from sqlalchemy import event
from sqlalchemy.engine import Engine

logger = logging.getLogger("indogist.database")


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if "sqlite" in settings.DATABASE_URL or type(dbapi_connection).__module__.startswith("sqlite3"):
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()
        except Exception:
            pass


def init_engine():
    db_url = settings.DATABASE_URL
    connect_args = {"check_same_thread": False} if "sqlite" in db_url else {}

    try:
        test_engine = create_engine(db_url, echo=False, connect_args=connect_args)
        with test_engine.connect() as conn:
            pass
        return test_engine
    except Exception as e:
        logger.warning(
            "Primary database at %s unreachable: %s. Falling back to SQLite.", db_url, e
        )
        fallback_url = "sqlite:///./db.sqlite3"
        settings.DATABASE_URL = fallback_url
        fallback_engine = create_engine(
            fallback_url, echo=False, connect_args={"check_same_thread": False}
        )
        try:
            SQLModel.metadata.create_all(fallback_engine)
        except Exception:
            pass
        return fallback_engine


engine = init_engine()


def create_db_and_tables():
    global engine
    try:
        SQLModel.metadata.create_all(engine)
    except Exception as e:
        logger.warning(
            "Error during create_db_and_tables: %s. Re-initializing SQLite fallback.", e
        )
        fallback_url = "sqlite:///./db.sqlite3"
        settings.DATABASE_URL = fallback_url
        engine = create_engine(
            fallback_url, echo=False, connect_args={"check_same_thread": False}
        )
        SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
