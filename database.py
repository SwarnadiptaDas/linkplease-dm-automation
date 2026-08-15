import asyncio
from datetime import datetime, timezone
import json
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

DATABASE_URL = "sqlite+aiosqlite:///./linkplease.db"

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

def now_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class Rule(Base):
    __tablename__ = "rules"
    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(String, unique=True, index=True)
    keyword = Column(String, index=True)
    dm_message = Column(Text)

class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    event_id = Column(String, primary_key=True)
    event_type = Column(String)
    data_json = Column(Text)
    status = Column(String, default="pending")  # pending, processed
    created_at = Column(DateTime, default=now_utc)

class DMTask(Base):
    __tablename__ = "dm_tasks"
    id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(String, index=True)
    rule_id = Column(String)
    recipient_user_id = Column(String)
    message = Column(Text)
    
    status = Column(String, default="queued")  # queued, accepted, delivered, failed
    dm_id = Column(String, nullable=True, index=True)
    
    next_attempt_at = Column(DateTime, default=now_utc)
    error_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=now_utc)
    updated_at = Column(DateTime, default=now_utc, onupdate=now_utc)

class RuleExecution(Base):
    """To prevent duplicate DMs for the same rule & user."""
    __tablename__ = "rule_executions"
    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(String, index=True)
    user_id = Column(String, index=True)
    created_at = Column(DateTime, default=now_utc)

class StatStore(Base):
    __tablename__ = "stat_store"
    key = Column(String, primary_key=True)
    value = Column(Integer, default=0)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
