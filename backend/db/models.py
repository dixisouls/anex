"""
ORM models.

These are deliberately separate from Pydantic shapes in contracts/schemas.py.
Postgres is the source of truth; Redis holds rebuildable projections.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
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

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    credits: Mapped[float] = mapped_column(Numeric(14, 2), default=0.0)
    is_sim: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    tasks: Mapped[list["Task"]] = relationship(back_populates="user")


class Model(Base):
    __tablename__ = "models"

    model_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    provider: Mapped[str] = mapped_column(String(16))
    tier: Mapped[str] = mapped_column(String(16))
    executable: Mapped[bool] = mapped_column(Boolean, default=True)
    pool_shares: Mapped[float] = mapped_column(Numeric(18, 6))
    pool_credits: Mapped[float] = mapped_column(Numeric(18, 6))
    ipo_price: Mapped[float] = mapped_column(Numeric(12, 4))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Agent(Base):
    __tablename__ = "agents"

    agent_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    capability_id: Mapped[str] = mapped_column(String(64), index=True)
    service_tier: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(255))
    skills: Mapped[list] = mapped_column(JSONB, default=list)
    capability_text: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(128), ForeignKey("models.model_id"))
    tools: Mapped[list] = mapped_column(JSONB, default=list)
    margin: Mapped[float] = mapped_column(Numeric(6, 4), default=0.2)
    reputation: Mapped[float] = mapped_column(Numeric(5, 4), default=0.5)
    credits: Mapped[float] = mapped_column(Numeric(12, 2), default=100.0)
    hires: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    service_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    goal: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="posted")
    hidden_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    user: Mapped["User | None"] = relationship(back_populates="tasks")
    subtasks: Mapped[list["Subtask"]] = relationship(
        back_populates="task", order_by="Subtask.order_index"
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
    candidates_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    hire_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    budget_remaining: Mapped[float | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    skipped: Mapped[bool] = mapped_column(Boolean, default=False)
    skip_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    skip_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    task: Mapped["Task"] = relationship(back_populates="subtasks")


class Holding(Base):
    __tablename__ = "holdings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    model_id: Mapped[str] = mapped_column(ForeignKey("models.model_id"))
    shares: Mapped[float] = mapped_column(Numeric(18, 6), default=0.0)


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    model_id: Mapped[str] = mapped_column(ForeignKey("models.model_id"))
    side: Mapped[str] = mapped_column(String(4))
    shares: Mapped[float] = mapped_column(Numeric(18, 6))
    credits: Mapped[float] = mapped_column(Numeric(18, 6))
    price: Mapped[float] = mapped_column(Numeric(12, 4))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.agent_id"))
    task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    model_id: Mapped[str | None] = mapped_column(
        ForeignKey("models.model_id"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(20))
    credits_delta: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    reputation_before: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    reputation_after: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
