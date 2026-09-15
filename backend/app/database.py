from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

load_dotenv()

from app.config import settings

DATABASE_URL = settings.database_url


def _psycopg_database_url(url: str) -> str:
    """Select the installed Psycopg 3 driver for platform-provided URLs."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url

engine = create_engine(
    _psycopg_database_url(DATABASE_URL),
    pool_pre_ping=True,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_recycle=settings.database_pool_recycle_seconds,
    pool_timeout=settings.database_pool_timeout_seconds,
)

SessionLocal = sessionmaker(autocommit=False, 
                            autoflush=False, 
                            bind=engine)


class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
