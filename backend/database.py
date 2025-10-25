import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv() # Make sure environment variables are loaded

DATABASE_URL = os.getenv("DATABASE_URL")

# Check if DATABASE_URL is loaded correctly
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set or .env file not loaded.")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependency function to get a DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

        