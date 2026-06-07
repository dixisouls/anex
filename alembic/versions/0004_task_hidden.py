"""task hidden_at for user-side soft delete

Revision ID: 0004_task_hidden
Revises: 0003_agent_tiers
Create Date: 2026-06-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_task_hidden"
down_revision: Union[str, None] = "0003_agent_tiers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("hidden_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tasks", "hidden_at")
