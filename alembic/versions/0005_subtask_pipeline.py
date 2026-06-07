"""subtask pipeline persistence (candidates, hire, skip)

Revision ID: 0005_subtask_pipeline
Revises: 0004_task_hidden
Create Date: 2026-06-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0005_subtask_pipeline"
down_revision: Union[str, None] = "0004_task_hidden"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "subtasks",
        sa.Column("candidates_json", JSONB, nullable=True),
    )
    op.add_column(
        "subtasks",
        sa.Column("hire_price", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "subtasks",
        sa.Column("budget_remaining", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "subtasks",
        sa.Column("skipped", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "subtasks",
        sa.Column("skip_reason", sa.String(32), nullable=True),
    )
    op.add_column(
        "subtasks",
        sa.Column("skip_message", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("subtasks", "skip_message")
    op.drop_column("subtasks", "skip_reason")
    op.drop_column("subtasks", "skipped")
    op.drop_column("subtasks", "budget_remaining")
    op.drop_column("subtasks", "hire_price")
    op.drop_column("subtasks", "candidates_json")
