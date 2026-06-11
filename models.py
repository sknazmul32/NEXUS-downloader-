from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, index=True)  # ক্লায়েন্ট থেকে পাঠানো অনন্য ID
    downloads_today = Column(Integer, default=0)
    last_reset = Column(DateTime, default=datetime.utcnow)
    is_premium = Column(Boolean, default=False)
    premium_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Download(Base):
    __tablename__ = "downloads"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    url = Column(String)
    platform = Column(String)  # YouTube, Instagram, TikTok ইত্যাদি
    status = Column(String, default="pending")  # pending, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    transaction_id = Column(String, unique=True)
    amount = Column(Float)
    status = Column(String)  # success, failed, pending
    created_at = Column(DateTime, default=datetime.utcnow)
