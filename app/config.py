import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    SECRET_KEY: str = os.getenv("SECRET_KEY", "indogist-secret-key-change-in-production")
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/db.sqlite3")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
