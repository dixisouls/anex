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
PRICE_HISTORY_PREFIX = "price:history:"
MARKET_SESSION_KEY = "market:session"
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
# Judge can use a stronger/steadier model than the default chat model.
JUDGE_MODEL = os.getenv("JUDGE_MODEL", GCP_CHAT_MODEL)
GCP_EMBED_MODEL = os.getenv(
    "GCP_EMBED_MODEL", os.getenv("VERTEX_EMBED_MODEL", "gemini-embedding-001")
)

# OpenAI (worker variety + simulation)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-5.4-mini")

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

# Two-stage matching: cosine recall breadth, then LLM re-rank of finalists.
RANK_RECALL_K = int(os.getenv("RANK_RECALL_K", "10"))
RERANK_FINALISTS = int(os.getenv("RERANK_FINALISTS", "6"))

# Model exchange IPO defaults (fixed constants)
IPO_SHARES = float(os.getenv("IPO_SHARES", "1000"))
TIER_IPO_PRICE = {
    "pro": float(os.getenv("IPO_PRICE_PRO", "50")),
    "flash": float(os.getenv("IPO_PRICE_FLASH", "20")),
    "lite": float(os.getenv("IPO_PRICE_LITE", "8")),
}
USER_START_CREDITS = float(os.getenv("USER_START_CREDITS", "1000"))
SIM_POSTERS = int(os.getenv("SIM_POSTERS", "2"))
SIM_INVESTORS = int(os.getenv("SIM_INVESTORS", "8"))
SIM_CADENCE_S = float(os.getenv("SIM_CADENCE_S", "4.0"))
SIM_CADENCE_JITTER = float(os.getenv("SIM_CADENCE_JITTER", "0.5"))
TRADE_CAP = float(os.getenv("TRADE_CAP", "100"))
MAX_CONCURRENT_TASKS = int(os.getenv("MAX_CONCURRENT_TASKS", "2"))

# Shared agent worker pool: all agents route to one of these generic workers
# (the broker passes model config per dispatch, so any worker can run any agent).
AGENT_WORKERS = int(os.getenv("AGENT_WORKERS", "16"))
AGENT_WORKER_BASE_PORT = int(os.getenv("AGENT_WORKER_BASE_PORT", "9001"))

# Model exchange AMM tuning
EARN_RATE = float(os.getenv("EARN_RATE", "8.0"))
EARN_CLAMP = float(os.getenv("EARN_CLAMP", "200.0"))
# Earnings break-even: scores above push price up, below push it down.
EARN_BASELINE = float(os.getenv("EARN_BASELINE", "0.62"))
MIN_POOL_SHARES = 1.0
MIN_POOL_CREDITS = 1.0

# Market dynamics (fundamental fair value + microstructure)
FUNDAMENTAL_SCALE = float(os.getenv("FUNDAMENTAL_SCALE", "5000"))
POOL_PASS_THROUGH = float(os.getenv("POOL_PASS_THROUGH", "0.35"))
KAPPA_PRO = float(os.getenv("KAPPA_PRO", "0.08"))
KAPPA_FLASH = float(os.getenv("KAPPA_FLASH", "0.12"))
KAPPA_LITE = float(os.getenv("KAPPA_LITE", "0.18"))
SIGMA_PRO = float(os.getenv("SIGMA_PRO", "0.004"))
SIGMA_FLASH = float(os.getenv("SIGMA_FLASH", "0.008"))
SIGMA_LITE = float(os.getenv("SIGMA_LITE", "0.015"))
KAPPA_BY_TIER = {"pro": KAPPA_PRO, "flash": KAPPA_FLASH, "lite": KAPPA_LITE}
SIGMA_BY_TIER = {"pro": SIGMA_PRO, "flash": SIGMA_FLASH, "lite": SIGMA_LITE}
ARB_INTERVAL_S = float(os.getenv("ARB_INTERVAL_S", "2.0"))
ARB_MAX_BPS = float(os.getenv("ARB_MAX_BPS", "15.0"))
ARB_ENABLED = os.getenv("ARB_ENABLED", "1") == "1"
QUOTE_SIZE = float(os.getenv("QUOTE_SIZE", "10.0"))
HISTORY_PER_MODEL = int(os.getenv("HISTORY_PER_MODEL", "2000"))
POSTER_BUDGET_CAP = float(os.getenv("POSTER_BUDGET_CAP", "150.0"))
DEPTH_FRACTION = float(os.getenv("DEPTH_FRACTION", "0.02"))

# Ledger tuning
REP_ALPHA = float(os.getenv("REP_ALPHA", "0.3"))
AWARD_RATE = float(os.getenv("AWARD_RATE", "1.0"))
AWARD_FRACTION = float(os.getenv("AWARD_FRACTION", "0.15"))
UPGRADE_THRESHOLD = float(os.getenv("UPGRADE_THRESHOLD", "200.0"))

# Placeholder model price before live exchange reads (Branch 2 only)
PLACEHOLDER_MODEL_PRICE = float(os.getenv("PLACEHOLDER_MODEL_PRICE", "10.0"))

# Idempotency keys for scored subtasks
SCORED_PREFIX = "scored:"
