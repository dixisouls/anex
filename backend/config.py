"""
Central configuration for the backend.
"""

import os

# Redis connection
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Postgres connection
# SQLAlchemy async URL form, asyncpg driver. The same driver backs Alembic, so
# there is only one Postgres driver in the project.
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+asyncpg://bazaar:bazaar@localhost:5432/bazaar",
)

# Echo SQL to stdout when debugging. Off by default.
SQL_ECHO = os.getenv("SQL_ECHO", "0") == "1"

# Redis keys and index names (must match contracts/CONTRACTS.md)
AGENT_PREFIX = "agent:"
TASK_PREFIX = "task:"
LEADERBOARD_KEY = "leaderboard"
STREAM_KEY = "market:feed"
INDEX_NAME = os.getenv("INDEX_NAME", "agents_idx")
VECTOR_FIELD = "embedding"

# Vector index. DIM must be equal to embedding model's output dimension.
# 768 is the text-embedding-005 default and local fallback dimension.
# If changing the model, change this 
VECTOR_DIM = int(os.getenv("VECTOR_DIM", "768"))
VECTOR_METRIC = "COSINE"

# Embeddings. "local" is a deterministic offline fallback so initial dev runs without GCP.
# "vertex" calls vertex ai (now agent platform but we still use old naming)
EMBED_BACKEND = os.getenv("EMBED_BACKEND", "local")
VERTEX_PROJECT = os.getenv("VERTEX_PROJECT", "")
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")
VERTEX_EMBED_MODEL = os.getenv("VERTEX_EMBED_MODEL", "text-embedding-005")

# Broker rank weights. Defined as a single source of truth
# the frontend formula note and the broker agree. final = w_match * match + 
# w_reputation * reputation - w_price * price. Keep them as fixed constants
W_MATCH = float(os.getenv("W_MATCH", "1.0"))
W_REP = float(os.getenv("W_REP", "0.5"))
W_PRICE = float(os.getenv("W_PRICE", "0.05"))
