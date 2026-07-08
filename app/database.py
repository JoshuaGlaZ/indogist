import logging
from typing import Generator
from sqlmodel import SQLModel, create_engine, Session
from app.config import settings

logger = logging.getLogger("indogist.database")

def init_engine():
    db_url = settings.DATABASE_URL
    connect_args = {"check_same_thread": False} if "sqlite" in db_url else {}
    
    try:
        test_engine = create_engine(db_url, echo=False, connect_args=connect_args)
        # Test connection
        with test_engine.connect() as conn:
            pass
        return test_engine
    except Exception as e:
        print(f"[Database Warning] Primary database at {db_url} unreachable: {e}. Falling back to SQLite.")
        fallback_url = "sqlite:///./db.sqlite3"
        settings.DATABASE_URL = fallback_url
        fallback_engine = create_engine(fallback_url, echo=False, connect_args={"check_same_thread": False})
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
        print(f"[Database Warning] Error during create_db_and_tables: {e}. Re-initializing SQLite fallback.")
        fallback_url = "sqlite:///./db.sqlite3"
        settings.DATABASE_URL = fallback_url
        engine = create_engine(fallback_url, echo=False, connect_args={"check_same_thread": False})
        SQLModel.metadata.create_all(engine)

def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
