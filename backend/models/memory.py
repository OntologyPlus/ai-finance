from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, JSON, func

from models.database import Base


class MemoryEntry(Base):
    __tablename__ = "memory_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False, index=True)
    memory_type = Column(String(20), nullable=False)  # working/episodic/semantic/procedural
    content = Column(Text, nullable=False)
    importance = Column(Float, default=0.5)
    embedding = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    accessed_at = Column(DateTime, onupdate=func.now())
    access_count = Column(Integer, default=0)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), unique=True, nullable=False, index=True)
    role = Column(String(50), default="")
    department = Column(String(100), default="")
    preferences = Column(JSON, default=dict)
    behavior_patterns = Column(JSON, default=list)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ProceduralRule(Base):
    __tablename__ = "procedural_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False, index=True)
    pattern = Column(String(200), nullable=False)
    success_rate = Column(Float, default=0.5)
    execution_count = Column(Integer, default=0)
    last_used = Column(DateTime, server_default=func.now())
