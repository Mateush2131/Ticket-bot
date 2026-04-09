from sqlalchemy import Column, Integer, String, DateTime, Float, Enum, JSON, BigInteger, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()

class UserRole(enum.Enum):
    ADMIN = "admin"
    MODERATOR = "moderator"
    USER = "user"
    PENDING = "pending"
    BANNED = "banned"

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    role = Column(Enum(UserRole), default=UserRole.PENDING)
    admin_nick = Column(String(20))
    admin_password_hash = Column(String(255))
    date_joined = Column(DateTime)
    wallet_address = Column(String(255))
    total_profit = Column(Float, default=0.0)
    daily_profit = Column(Float, default=0.0)
    commission_rate = Column(Integer, default=10)
    referral_id = Column(Integer, nullable=True)
    referral_link = Column(String(255), nullable=True)
    form_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class Application(Base):
    __tablename__ = 'applications'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    answers = Column(JSON)
    status = Column(String(20), default="pending")
    moderated_by = Column(Integer, nullable=True)
    moderated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

class AdminLog(Base):
    __tablename__ = 'admin_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_id = Column(Integer, nullable=False)
    action = Column(String(100))
    target_user_id = Column(Integer, nullable=True)
    details = Column(JSON)
    created_at = Column(DateTime, default=datetime.now)

class Transaction(Base):
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    amount = Column(Float, nullable=False)
    wallet = Column(String(255))
    status = Column(String(20), default="pending")
    description = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    completed_at = Column(DateTime, nullable=True)
    
    user = relationship("User", backref="transactions")

class Referral(Base):
    __tablename__ = 'referrals'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    clicks = Column(Integer, default=0)
    registrations = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    
    owner = relationship("User", backref="referrals")