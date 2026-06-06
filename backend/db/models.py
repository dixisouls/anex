"""
ORM models.

THese are deliberately seperate from Pydantic shapes in contracts/schemas.py.
The Pydantic Agent is the API and transport shape; this Agent is how it is
stored. The repo layer maps between them. Keeping them apart means a storage
change (a column, an index) never forces a contract change.

Source of truth lives here. Redis holds projection (the vector index, the 
leaderboard, the feed) that are rebuildable from these tables.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        
    )
    email: Mapped[str] = mapped_column(
        String(320),
        unique=True,
        index=True,
        
    )
    # nullable until auth is built
    password_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="user",
    )

class Agent(Base):
    __tablename__ = "agents"

    
    agent_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    skills: Mapped[list] = mapped_column(JSONB, default=list)
    capability_text: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(128))
    tools: Mapped[list] = mapped_column(JSONB, default=list)
    price: Mapped[float] = mapped_column(Numeric(10, 2), default=5.0)
    reputation: Mapped[float] = mapped_column(Numeric(5, 4), default=0.5)
    credits: Mapped[float] = mapped_column(Numeric(12, 2), default=100.0)
    hires: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    service_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )
    goal: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="posted")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    user: Mapped["User | None"] = relationship(back_populates="tasks")
    subtasks: Mapped[list["Subtask"]] = relationship(
        back_populates="task",
        order_by="Subtask.order_index",
    )

class Subtask(Base):
    __tablename__ = "subtasks"
 
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"))
    order_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    assigned_agent_id: Mapped[str | None] = mapped_column(
        ForeignKey("agents.agent_id"), nullable=True
    )
    output_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    judge_score: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
 
    task: Mapped["Task"] = relationship(back_populates="subtasks")
 
 
class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
 
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.agent_id"))
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tasks.id"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(20))  # hire, award, upgrade
    credits_delta: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    reputation_before: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    reputation_after: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
