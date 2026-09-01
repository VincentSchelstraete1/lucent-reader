from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

load_dotenv()

from app.config import settings

DATABASE_URL = settings.database_url

engine = create_engine(DATABASE_URL)

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
