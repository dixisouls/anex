"""agent tiers: capability_id and service_tier on agents

Revision ID: 0003_agent_tiers
Revises: 0002_exchange
Create Date: 2026-06-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_agent_tiers"
down_revision: Union[str, None] = "0002_exchange"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("capability_id", sa.String(length=64), nullable=False, server_default="unknown"),
    )
    op.add_column(
        "agents",
        sa.Column("service_tier", sa.String(length=16), nullable=False, server_default="flash"),
    )
    op.create_index(op.f("ix_agents_capability_id"), "agents", ["capability_id"], unique=False)
    op.alter_column("agents", "capability_id", server_default=None)
    op.alter_column("agents", "service_tier", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_agents_capability_id"), table_name="agents")
    op.drop_column("agents", "service_tier")
    op.drop_column("agents", "capability_id")
