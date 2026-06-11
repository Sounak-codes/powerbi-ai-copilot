"""
PostgreSQL database models.
"""
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Float, JSON, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    """User model."""
    __tablename__ = "users"
    
    id = Column(String, primary_key=True)
    email = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    conversations = relationship("Conversation", back_populates="user")
    sessions = relationship("Session", back_populates="user")


class Conversation(Base):
    """Conversation model."""
    __tablename__ = "conversations"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))
    session_id = Column(String, ForeignKey("sessions.id"))
    title = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="conversations")
    session = relationship("Session", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation")


class Message(Base):
    """Message model."""
    __tablename__ = "messages"
    
    id = Column(String, primary_key=True)
    conversation_id = Column(String, ForeignKey("conversations.id"))
    role = Column(String)  # "user", "assistant", "system"
    content = Column(Text)
    metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    conversation = relationship("Conversation", back_populates="messages")


class Session(Base):
    """Session model."""
    __tablename__ = "sessions"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))
    report_id = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    expired_at = Column(DateTime)
    
    user = relationship("User", back_populates="sessions")
    conversations = relationship("Conversation", back_populates="session")


class Insight(Base):
    """Insight model."""
    __tablename__ = "insights"
    
    id = Column(String, primary_key=True)
    session_id = Column(String)
    type = Column(String)
    title = Column(String)
    description = Column(Text)
    metrics = Column(JSON)
    confidence = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)


class Feedback(Base):
    """User feedback model."""
    __tablename__ = "feedback"
    
    id = Column(String, primary_key=True)
    message_id = Column(String)
    session_id = Column(String)
    rating = Column(Integer)
    comment = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
