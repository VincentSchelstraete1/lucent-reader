import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy import sessionmaker

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, 
                            autoflush=False, 
                            bind=engine)

db = SessionLocal()
