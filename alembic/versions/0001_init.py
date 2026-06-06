"""init

Revision ID: 0001_init
Revises:
Create Date: 2026-06-06

Hand-written so `alembic upgrade head` works on a fresh database with no
autogenerate step. For later schema changes, edit backend/db/models.py and run
`alembic revision --autogenerate -m "your message"`.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_init"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "agents",
        sa.Column("agent_id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("skills", postgresql.JSONB(), nullable=False),
        sa.Column("capability_text", sa.Text(), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("tools", postgresql.JSONB(), nullable=False),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("reputation", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("credits", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("hires", sa.Integer(), nullable=False),
        sa.Column("wins", sa.Integer(), nullable=False),
        sa.Column("service_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "subtasks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("task_id", sa.Uuid(), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("assigned_agent_id", sa.String(length=64), sa.ForeignKey("agents.agent_id"), nullable=True),
        sa.Column("output_preview", sa.Text(), nullable=True),
        sa.Column("judge_score", sa.Numeric(precision=5, scale=4), nullable=True),
    )

    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("agent_id", sa.String(length=64), sa.ForeignKey("agents.agent_id"), nullable=False),
        sa.Column("task_id", sa.Uuid(), sa.ForeignKey("tasks.id"), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("credits_delta", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("reputation_before", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("reputation_after", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ledger_entries")
    op.drop_table("subtasks")
    op.drop_table("tasks")
    op.drop_table("agents")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")