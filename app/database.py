from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Database Setup
IS_VERCEL = os.environ.get("VERCEL") == "1"

if IS_VERCEL:
    # Use /tmp for ephemeral storage on Vercel
    SQLALCHEMY_DATABASE_URL = "sqlite:////tmp/idcdetect.db"
else:
    # Local persistent DB
    SQLALCHEMY_DATABASE_URL = "sqlite:///./idcdetect.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
