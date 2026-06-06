"""
Central configuration for the backend.
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass

# Local↔cloud seam: selects Queue + EventBus adapters (ports/factory.py)
RUNTIME_ENV = os.getenv("RUNTIME_ENV", "local")  # "local" | "gcp"

# Redis connection
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Postgres connection
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://bazaar:bazaar@localhost:5432/bazaar",
)

SQL_ECHO = os.getenv("SQL_ECHO", "0") == "1"

# Redis keys and index names
AGENT_PREFIX = "agent:"
MODEL_PREFIX = "model:"
TASK_PREFIX = "task:"
LEADERBOARD_KEY = "leaderboard"
MODEL_PRICES_KEY = "model_prices"
PRICE_HISTORY_KEY = "price:history"
STREAM_KEY = "market:feed"
INDEX_NAME = os.getenv("INDEX_NAME", "agents_idx")
VECTOR_FIELD = "embedding"

# Vector index. DIM must match the embedding model output dimension.
VECTOR_DIM = int(os.getenv("VECTOR_DIM", "768"))
VECTOR_METRIC = "COSINE"

# GCP Gemini Enterprise Agent Platform (google-genai)
GCP_PROJECT = os.getenv("GCP_PROJECT", os.getenv("VERTEX_PROJECT", ""))
GCP_LOCATION = os.getenv("GCP_LOCATION", os.getenv("VERTEX_LOCATION", "global"))
GCP_CHAT_MODEL = os.getenv("GCP_CHAT_MODEL", "gemini-3.5-flash")
GCP_EMBED_MODEL = os.getenv(
    "GCP_EMBED_MODEL", os.getenv("VERTEX_EMBED_MODEL", "gemini-embedding-001")
)

# OpenAI (worker variety + simulation)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini")

# Cloud-only names (read by GCP adapters in Branch 7; harmless defaults locally)
API_URL = os.getenv("API_URL", "http://localhost:8000")
PUBSUB_TOPIC = os.getenv("PUBSUB_TOPIC", "market-feed")
PUBSUB_SUB = os.getenv("PUBSUB_SUB", "market-feed-sse")
TASKS_INVOKER_SA = os.getenv("TASKS_INVOKER_SA", "")

# Weave observability
WEAVE_PROJECT = os.getenv("WEAVE_PROJECT", "agent-bazaar")
WEAVE_DISABLED = os.getenv("WEAVE_DISABLED", "0") == "1"

# Broker rank weights
W_MATCH = float(os.getenv("W_MATCH", "1.0"))
W_REP = float(os.getenv("W_REP", "0.5"))
W_PRICE = float(os.getenv("W_PRICE", "0.05"))

# Model exchange IPO defaults (fixed constants)
IPO_SHARES = float(os.getenv("IPO_SHARES", "1000"))
TIER_IPO_PRICE = {
    "pro": float(os.getenv("IPO_PRICE_PRO", "50")),
    "flash": float(os.getenv("IPO_PRICE_FLASH", "20")),
    "lite": float(os.getenv("IPO_PRICE_LITE", "8")),
}
USER_START_CREDITS = float(os.getenv("USER_START_CREDITS", "1000"))
SIM_POSTERS = int(os.getenv("SIM_POSTERS", "2"))
SIM_INVESTORS = int(os.getenv("SIM_INVESTORS", "3"))
SIM_CADENCE_S = float(os.getenv("SIM_CADENCE_S", "8.0"))
TRADE_CAP = float(os.getenv("TRADE_CAP", "100"))

# Model exchange AMM tuning
EARN_RATE = float(os.getenv("EARN_RATE", "20.0"))
EARN_CLAMP = float(os.getenv("EARN_CLAMP", "200.0"))
MIN_POOL_SHARES = 1.0
MIN_POOL_CREDITS = 1.0

# Ledger tuning
REP_ALPHA = float(os.getenv("REP_ALPHA", "0.3"))
AWARD_RATE = float(os.getenv("AWARD_RATE", "1.0"))
UPGRADE_THRESHOLD = float(os.getenv("UPGRADE_THRESHOLD", "200.0"))

# Placeholder model price before live exchange reads (Branch 2 only)
PLACEHOLDER_MODEL_PRICE = float(os.getenv("PLACEHOLDER_MODEL_PRICE", "10.0"))

# Idempotency keys for scored subtasks
SCORED_PREFIX = "scored:"
