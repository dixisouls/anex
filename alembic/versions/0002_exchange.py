"""exchange: models, holdings, trades; user credits; agent margin

Revision ID: 0002_exchange
Revises: 0001_init
Create Date: 2026-06-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_exchange"
down_revision: Union[str, None] = "0001_init"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# IPO rows so agent.model FK succeeds on upgrade from a seeded 0001 database.
_SEED_MODELS = [
    ("gemini-3.1-pro-preview", "Gemini 3.1 Pro", "gcp", "pro", 50.0),
    ("gemini-3.5-flash", "Gemini 3.5 Flash", "gcp", "flash", 20.0),
    ("gemini-3.1-flash-lite", "Gemini Flash Lite", "gcp", "lite", 8.0),
    ("gemma-4-26b-a4b-it", "Gemma 4 26B", "gcp", "lite", 8.0),
    ("gpt-4.1-mini", "GPT-4.1 Mini", "openai", "flash", 20.0),
    ("gpt-4.1", "GPT-4.1", "openai", "pro", 50.0),
]
_IPO_SHARES = 1000.0


def upgrade() -> None:
    op.create_table(
        "models",
        sa.Column("model_id", sa.String(length=128), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("tier", sa.String(length=16), nullable=False),
        sa.Column("executable", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("pool_shares", sa.Numeric(18, 6), nullable=False),
        sa.Column("pool_credits", sa.Numeric(18, 6), nullable=False),
        sa.Column("ipo_price", sa.Numeric(12, 4), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    models_table = sa.table(
        "models",
        sa.column("model_id", sa.String),
        sa.column("name", sa.String),
        sa.column("provider", sa.String),
        sa.column("tier", sa.String),
        sa.column("executable", sa.Boolean),
        sa.column("pool_shares", sa.Numeric),
        sa.column("pool_credits", sa.Numeric),
        sa.column("ipo_price", sa.Numeric),
    )
    op.bulk_insert(
        models_table,
        [
            {
                "model_id": mid,
                "name": name,
                "provider": provider,
                "tier": tier,
                "executable": True,
                "pool_shares": _IPO_SHARES,
                "pool_credits": ipo * _IPO_SHARES,
                "ipo_price": ipo,
            }
            for mid, name, provider, tier, ipo in _SEED_MODELS
        ],
    )

    op.add_column(
        "users",
        sa.Column("credits", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "users",
        sa.Column("is_sim", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    op.add_column(
        "agents",
        sa.Column("margin", sa.Numeric(6, 4), nullable=False, server_default=sa.text("0.2")),
    )
    op.drop_column("agents", "price")
    op.execute(
        "UPDATE agents SET model = 'gemini-3.1-flash-lite' "
        "WHERE model = 'gemini-3.1-flash-lite-preview'"
    )
    op.create_foreign_key("fk_agents_model", "agents", "models", ["model"], ["model_id"])
    op.alter_column("agents", "name", type_=sa.String(length=255))

    op.create_table(
        "holdings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("model_id", sa.String(length=128), sa.ForeignKey("models.model_id"), nullable=False),
        sa.Column("shares", sa.Numeric(18, 6), nullable=False, server_default=sa.text("0")),
    )
    op.create_unique_constraint("uq_holdings_user_model", "holdings", ["user_id", "model_id"])

    op.create_table(
        "trades",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("model_id", sa.String(length=128), sa.ForeignKey("models.model_id"), nullable=False),
        sa.Column("side", sa.String(length=4), nullable=False),
        sa.Column("shares", sa.Numeric(18, 6), nullable=False),
        sa.Column("credits", sa.Numeric(18, 6), nullable=False),
        sa.Column("price", sa.Numeric(12, 4), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.add_column(
        "ledger_entries",
        sa.Column("model_id", sa.String(length=128), sa.ForeignKey("models.model_id"), nullable=True),
    )
    op.add_column(
        "ledger_entries",
        sa.Column("amount", sa.Numeric(14, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ledger_entries", "amount")
    op.drop_column("ledger_entries", "model_id")
    op.drop_table("trades")
    op.drop_constraint("uq_holdings_user_model", "holdings", type_="unique")
    op.drop_table("holdings")
    op.alter_column("agents", "name", type_=sa.String(length=200))
    op.drop_constraint("fk_agents_model", "agents", type_="foreignkey")
    op.add_column(
        "agents",
        sa.Column("price", sa.Numeric(10, 2), nullable=False, server_default=sa.text("5.0")),
    )
    op.drop_column("agents", "margin")
    op.drop_column("users", "is_sim")
    op.drop_column("users", "credits")
    op.drop_table("models")
