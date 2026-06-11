from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base
from config import DATABASE_URL

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine
)

def init_db():
    """ডাটাবেস টেবিল তৈরি করুন"""
    Base.metadata.create_all(bind=engine)

def get_db():
    """ডাটাবেস সেশন প্রদান করুন"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
