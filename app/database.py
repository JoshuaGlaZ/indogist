from typing import Generator
from sqlmodel import SQLModel, create_engine, Session
from app.config import settings

# SQLite specific connect args for thread safety if needed
connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}

engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args=connect_args
)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
