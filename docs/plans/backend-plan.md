# Agent Bazaar Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Canonical location note:** The `writing-plans` skill prescribes `docs/superpowers/plans/YYYY-MM-DD-<feature>.md`. Per the user's explicit request this plan lives at `docs/plans/backend-plan.md` for easy discovery. If you adopt the skill convention later, copy/symlink it to `docs/superpowers/plans/2026-06-06-agent-bazaar-backend.md`.

**Goal:** Build the Agent Bazaar backend described in `build_doc.md`: two coupled markets (an agent marketplace and a constant-product model exchange) wired through Postgres + Redis, real GCP (`google-genai`) and OpenAI model calls, an OpenAI-driven simulation layer, and mandatory Weave tracing. No frontend.

**Architecture:** Postgres (SQLAlchemy async + Alembic) is the durable source of truth; Redis 8 holds hot-path projections (KNN vector index, leaderboard, live model prices, the `market:feed` stream). A broker decomposes goals and hires agents by KNN match + reputation − **derived price**, where an agent's hire price is `model_price(agent.model) * (1 + agent.margin)`. A judge scores outputs; the ledger updates reputation/credits and **injects earnings into the agent's model stock** through a constant-product AMM. Investors trade model shares through the same AMM. OpenAI sim agents post tasks and trade to drive a live demo. Weave traces every LLM call and every exchange operation.

**Cloud seam (ports/adapters).** The broker/ledger/exchange/API/sim depend only on three interfaces — `Queue` (hire dispatch), `EventBus` (event publish/subscribe), `Embeddings` (text→vector) — selected by one env flag, `RUNTIME_ENV` (`local` | `gcp`). Locally: in-process HTTP dispatch, Redis Stream events, GCP embeddings. In cloud: **Cloud Tasks** dispatch (HTTP push + OIDC), **Pub/Sub** event fan-out (Redis Stream kept as replay log), GCP embeddings. Redis is present in **both** environments (Memorystore in cloud) for the hot path. **Embeddings are GCP-only** (the local-hash fallback is removed; tests inject a fake). Full design: `docs/cloud-architecture.md`. This plan threads the seam through Branches 0/1/2 and provisions GCP in the new Branch 7 (`feat/cloud-infra`).

**Tech Stack (versions verified 2026-06-06; see `docs/cloud-architecture.md` §13):** Python 3.12, FastAPI 0.136.3, SQLAlchemy 2.0.50 (async) + asyncpg 0.31, Alembic 1.18.4, `redis` 8.0 (`redis.asyncio`, native vector KNN; Memorystore 7.2+ compatible), `google-genai` 2.8, `openai` 2.41, `weave` 0.52.42, `sse-starlette` 3.4.4, `httpx` 0.28.1, Docker Compose (Postgres 16 + Redis 8), pytest 8.4 + pytest-asyncio 1.4. Cloud adapters: `google-cloud-tasks` 2.22, `google-cloud-pubsub` 2.38, `google-cloud-secret-manager` 2.28, `cloud-sql-python-connector[asyncpg]` 1.20.3.

---

## How to read this plan

The plan is organized **branch-by-branch**, aligned to the `build_doc.md` §8 phase order. Each branch has two clearly separated parts, in this order (the user wants fixes first, then new code):

1. **Updates & cleanups** — changes to existing files that MUST happen on/before that branch.
2. **New content** — new modules/files, signatures, data structures, math, migrations, routes, Weave hooks, and a per-branch verification step.

Branch sequence (build these in order, each branching from the previous):

| # | Branch | Base | build_doc phase | Outcome |
|---|---|---|---|---|
| 0 | `feat/contracts-finalize` | `feat/market-core` | Phase 0 finalize | Contracts locked: events, schemas (margin not price), CONTRACTS.md filled, deps + config + repo cleanups, smoke test renamed |
| 1 | `feat/persistence-exchange` | `feat/contracts-finalize` | Phase 1 | `models`/`holdings`/`trades` tables, users get `credits`+`is_sim`, agents get `margin`+model FK (drop `price`), embeddings → `google-genai`, seeder lists models + sim users |
| 2 | `feat/agent-loop` | `feat/persistence-exchange` | Phase 2 | Agent base service + model router, seed agent services, judge, broker (decompose/match/rank/hire over HTTP) with placeholder model price, FastAPI app (`/agents`,`/task`,`/feed`,`/seed`), Weave on every LLM call. One task runs end-to-end. |
| 3 | `feat/ledger-exchange` | `feat/agent-loop` | Phase 3 | Ledger (reputation EMA, credits, earnings), AMM (list/buy/sell/inject), broker switched to live model price. Tasks move reputation/credits and model prices move on earnings. |
| 4 | `feat/investing-users` | `feat/ledger-exchange` | Phase 4 | `/models`,`/market`,`/trade`,`/portfolio/{id}`,`/users` (POST/GET), holdings + P&L. A user can buy a stock and revalue. |
| 5 | `feat/simulation` | `feat/investing-users` | Phase 5 | OpenAI task-poster + investor sims, `/sim/start`,`/sim/stop`. One button runs the whole system. |
| 6 | `feat/weave-upgrade` | `feat/simulation` | Phase 6 | Upgrade logic (margin/model-swap/tool), Weave custom views (success rate, cost/task, price history, portfolio returns). Full demo story. |
| 7 | `feat/cloud-infra` | `feat/weave-upgrade` | build_doc §6 + `docs/cloud-architecture.md` | GCP adapters (Cloud Tasks `Queue`, Pub/Sub `EventBus`, Cloud SQL connector wiring) + deployment: Artifact Registry, Cloud Run services/jobs, per-agent Cloud Tasks queues, Pub/Sub topic+sub, Cloud SQL + Memorystore over a VPC connector, Secret Manager, IAM, deploy scripts. `RUNTIME_ENV=gcp` runs end-to-end on GCP. |

**Note on the seam:** the *port interfaces* and the *local adapters* are introduced early (Branch 0 defines the interfaces; Branch 2 wires the broker/feed to use them with local adapters). Branch 7 only adds the **GCP adapters + infra** — so the cloud cutover is an adapter swap, not a rewrite. This supersedes the old "Cloud Run cutover is out of scope" note: cloud is now an explicit branch.

**Merge strategy:** chain the branches (each off the previous). Merge forward only — after a branch is verified, the next branch rebases/merges it in. At the end, open a PR chain into `main` (or a `develop` integration branch) in branch order 0→7 so each PR is small and reviewable. Never squash a later branch onto `main` before its predecessor. Gap-driven synthesis (build_doc §8 stretch) remains **out of scope** for this pass; note it as a future branch `feat/agent-synthesis`.

**Conventions used throughout:**
- All Redis-touching functions are async and take the client `r` first.
- All Postgres-touching functions take an `AsyncSession` (from `backend.infra.db.session_scope` or the FastAPI `get_session` dependency).
- Repo layer is the only module that imports ORM models; everyone else speaks the Pydantic contract shapes in `contracts/`.
- Money math uses `Decimal` at the DB boundary but the AMM computes in `float` and rounds; see Branch 3 for the rule.
- Every LLM-calling function and every exchange operation is decorated `@weave.op`.

---

## Repo baseline (verified on `feat/market-core`, 2026-06-06)

What already exists and works (read before touching):
- `backend/config.py` — Redis/Postgres URLs, Redis key names, vector dims, embed backend (`local`/`vertex` — **both retired**, see Branch 0/1), broker weights `W_MATCH/W_REP/W_PRICE`. Branch 0 adds `RUNTIME_ENV` and GCP/OpenAI/Weave/exchange config.
- `backend/infra/redis_client.py` — shared async client, `decode_responses=False` (vectors are raw bytes). Unchanged; in cloud `REDIS_URL` points at Memorystore.
- `backend/infra/embeddings.py` — local feature-hash embedding (deterministic) + **deprecated `vertexai` SDK** path. **Both are replaced in Branch 1 by a GCP-only `Embeddings` adapter** (`google-genai`); there is no production local-hash path after Branch 1 (tests use a fake).
- `backend/infra/db.py` — async engine, `session_scope()`, `get_session()` FastAPI dep.
- `backend/infra/util.py` — `to_str()` bytes decoder.
- `backend/db/base.py` — `Base(DeclarativeBase)`.
- `backend/db/models.py` — ORM: `User`, `Agent`, `Task`, `Subtask`, `LedgerEntry`.
- `backend/db/repo.py` — agent upsert/get/list, `clear_market`, user create/get.
- `backend/market/registry.py` — Redis projection: `agent:{id}` hash, `agents_idx` FLAT COSINE index, `leaderboard` zset; pure (de)serializers; KNN `search`.
- `backend/market/feed.py` — `emit()` / `read_new()` over `market:feed` stream.
- `backend/market/seeder.py` — Postgres write then Redis projection.
- `backend/market/seed_agents.py` — 6 seed agents (with stored `price`).
- `backend/api/__init__.py` — **empty**.
- `alembic/env.py`, `alembic/versions/0001_init.py`, `alembic.ini` — async migration setup; init revision id `0001_init`.
- `tests/0001_init.py` — **misnamed smoke test** (everything references `tests.smoke_test`).
- `docker-compose.yml`, `Dockerfile`, `requirements.txt`.
- `contracts/schemas.py` (Agent has stored `price`), `contracts/events.py` (8 events), `contracts/CONTRACTS.md` (**empty**), `contracts/mock_events.json` (to retire).

### Pre-existing defects discovered during review (fix in the branch noted)

These are not invented work — they are real inconsistencies in the current tree:

1. **`tests/0001_init.py` is misnamed.** `docker-compose.yml` line 8 and `tests/0001_init.py:9` both say `python -m tests.smoke_test`, which does not resolve. → rename in Branch 0.
2. **`User` ORM model has no `name` column, but `alembic/versions/0001_init.py:28` creates `users.name NOT NULL` and `repo.create_user(...)` passes `name=name`.** So `create_user` would fail at runtime, and an autogenerate diff would try to DROP `users.name`. → reconcile in Branch 0/1 (add `name` to the ORM model).
3. **`agents.name` length mismatch:** ORM `String(255)` vs migration `String(200)`. With `compare_type=True` this shows as drift. → align to `String(255)` in the Branch 1 migration delta or leave 200 and change ORM; pick one (plan picks `String(255)`).
4. **`backend/infra/embeddings.py:23`** has a dead `from multiprocessing import Value` import. → removed in Branch 1 when `embeddings.py` is replaced by the GCP-only adapter.
5. **`backend/infra/embeddings.py` uses the deprecated `vertexai` SDK** and `requirements.txt` references `google-cloud-aiplatform`. → migrate to `google-genai` in Branch 1, **and remove the local-hash fallback** (embeddings are GCP-only per build_doc / `docs/cloud-architecture.md` §8). `requirements.txt` drops `google-cloud-aiplatform`/`vertexai` and pins `google-genai>=2.8`.
6. **`contracts/CONTRACTS.md` is empty** and is declared the written spec for Redis layout, Postgres tables, and API routes. → fill in Branch 0 and keep updated each branch.

---

## Branch 0 — `feat/contracts-finalize` (Phase 0 finalize)

**Base:** `feat/market-core`  ·  **Purpose:** lock the integration surfaces (events, schemas, written contract), update dependencies/config, and clear the small defects, so all later branches build against a stable contract. **No feature logic.**

### 0.1 Updates & cleanups

- [ ] **Rename the smoke test.** `git mv tests/0001_init.py tests/smoke_test.py`. Add `tests/__init__.py` (empty) if not present so `python -m tests.smoke_test` resolves. Update the docstring header in `tests/smoke_test.py` (it already says `python -m tests.smoke_test`, good). No code body change.

- [ ] **Reconcile the `User` ORM model with its migration** (`backend/db/models.py`). Add the missing `name` column so the ORM matches `0001_init.py`:

```python
class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))          # NEW: matches 0001_init
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    tasks: Mapped[list["Task"]] = relationship(back_populates="user")
```

(The `credits` and `is_sim` columns are added in Branch 1, not here, to keep this branch contract-only.)

- [ ] **Remove the dead import** in `backend/infra/embeddings.py:23`: delete `from multiprocessing import Value`.

- [ ] **Replace agent `price` with `margin` in `contracts/schemas.py`.** `price` becomes a *computed read-time* field, not stored. Update both `Agent` and `Candidate`:

```python
class Candidate(BaseModel):
    agent_id: str
    match_score: float    # cosine similarity 0..1
    reputation: float     # 0..1
    price: float          # DERIVED hire price = model_price(model) * (1 + margin)
    final_score: float    # w_match*match + w_rep*reputation - w_price*price

class Agent(BaseModel):
    agent_id: str
    name: str
    skills: list[str]
    capability_text: str
    model: str
    tools: list[str] = Field(default_factory=list)
    reputation: float = 0.5
    credits: float = 100.0
    margin: float = 0.2                 # REPLACES stored price
    price: float | None = None          # derived at read time; None until computed
    hires: int = 0
    wins: int = 0
    service_url: Optional[str] = None
```

Rationale for keeping `price` on the schema as `Optional`: `GET /agents` returns derived price (build_doc §3.2). The roster builder fills it; nobody stores it. `Candidate.price` stays required because it is always computed at rank time.

- [ ] **Add new Pydantic contract objects** to `contracts/schemas.py` for the exchange/investing surfaces (used by routes in Branches 3–4):

```python
class Model(BaseModel):
    model_id: str
    name: str
    provider: Literal["gcp", "openai"]
    tier: Literal["pro", "flash", "lite"]
    executable: bool = True
    shares: float
    credits: float
    price: float            # = credits / shares
    ipo_price: float

class Holding(BaseModel):
    model_id: str
    shares: float
    price: float            # current model price
    value: float            # shares * price

class Portfolio(BaseModel):
    user_id: str
    credits: float
    holdings: list[Holding]
    holdings_value: float
    total: float            # credits + holdings_value

class UserPublic(BaseModel):
    user_id: str
    name: str
    email: str | None = None
    credits: float
    is_sim: bool
    net_worth: float | None = None   # filled by GET /users leaderboard
```

- [ ] **Add the five new events** to `contracts/events.py` and extend the discriminated union + `MarketEvent` `Union[...]`:

```python
class ModelListed(EventBase):
    type: Literal["model_listed"] = "model_listed"
    model_id: str
    name: str
    provider: str            # "gcp" | "openai"
    tier: str                # "pro" | "flash" | "lite"
    ipo_price: float

class PriceChanged(EventBase):
    type: Literal["price_changed"] = "price_changed"
    model_id: str
    old: float
    new: float
    reason: str              # "trade" | "earnings" | "tick"

class EarningsInjected(EventBase):
    type: Literal["earnings_injected"] = "earnings_injected"
    model_id: str
    agent_id: str
    amount: float
    judge_score: float

class TradeExecuted(EventBase):
    type: Literal["trade_executed"] = "trade_executed"
    trade_id: str
    user_id: str
    model_id: str
    side: str                # "buy" | "sell"
    shares: float
    credits: float
    price: float

class PortfolioChanged(EventBase):
    type: Literal["portfolio_changed"] = "portfolio_changed"
    user_id: str
    credits: float
    holdings_value: float
    total: float
```

Then extend:

```python
MarketEvent = Annotated[
    Union[
        TaskPosted, CandidatesRanked, AgentHired, TaskExecuted, TaskScored,
        ReputationChanged, CreditsChanged, AgentUpgraded,
        ModelListed, PriceChanged, EarningsInjected, TradeExecuted, PortfolioChanged,
    ],
    Field(discriminator="type"),
]
```

- [ ] **Retire the static mock.** `git rm contracts/mock_events.json`. Grep first for references (`rg mock_events`); the seeder/registry/tests do not import it, so removal is safe. The market is now driven by the simulation layer (Branch 5).

- [ ] **Replace `requirements.txt`** with the verified-latest pins (already written to the repo root on 2026-06-06; sources in `docs/cloud-architecture.md` §13). Remove `google-cloud-aiplatform`/`vertexai`. The file is:

```text
# --- Core / hot path ---
redis>=8.0,<9            # native vector KNN (FLAT); Memorystore 7.2+ compatible
pydantic>=2.13.4,<3
numpy>=2.4.6,<2.5

# --- Persistence (async) ---
sqlalchemy[asyncio]>=2.0.50,<2.1
asyncpg>=0.31
alembic>=1.18.4

# --- Models (cloud only; no offline model OR embedding calls) ---
google-genai>=2.8,<3     # chat + embeddings (gemini-embedding-001)
openai>=2.41,<3

# --- API + broker HTTP + SSE ---
fastapi>=0.136.3
uvicorn[standard]>=0.49
httpx>=0.28.1,<1
sse-starlette>=3.4.4

# --- Observability (mandatory) ---
weave>=0.52.42

# --- Cloud adapters (RUNTIME_ENV=gcp; safe to install everywhere) ---
google-cloud-tasks>=2.22
google-cloud-pubsub>=2.38
google-cloud-secret-manager>=2.28
cloud-sql-python-connector[asyncpg]>=1.20.3

# --- Dev / test ---
pytest>=8.4
pytest-asyncio>=1.4
```

(Versions verified 2026-06-06. Re-check with `pip index versions <pkg>` if implementing later; do not invent versions.)

- [ ] **Add config keys** to `backend/config.py` (drop Vertex names, add the `RUNTIME_ENV` seam flag, GCP genai, OpenAI, Weave, exchange/ledger constants). **Remove the `EMBED_BACKEND` `local`/`vertex` concept entirely** — embeddings are GCP-only (a fake is used only in tests via `EMBEDDINGS_FAKE`):

```python
# --- Local<->cloud seam: selects Queue + EventBus adapters (ports/factory.py) ---
RUNTIME_ENV = os.getenv("RUNTIME_ENV", "local")   # "local" | "gcp"

# --- Models: GCP Gemini Enterprise Agent Platform via google-genai ---
GCP_PROJECT   = os.getenv("GCP_PROJECT", "")
GCP_LOCATION  = os.getenv("GCP_LOCATION", "us-central1")
GCP_CHAT_MODEL  = os.getenv("GCP_CHAT_MODEL", "gemini-3.5-flash")
GCP_EMBED_MODEL = os.getenv("GCP_EMBED_MODEL", "gemini-embedding-001")  # text-embedding-004 deprecated 2026-01-14

# --- OpenAI (worker variety + simulation) ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini")  # confirm exact id available (Q: gpt-5.5 family is current)

# Embeddings are GCP-only. No EMBED_BACKEND. Tests set EMBEDDINGS_FAKE=1 to inject a fake.

# --- Cloud-only names (read by GCP adapters in Branch 7; harmless defaults locally) ---
API_URL          = os.getenv("API_URL", "http://localhost:8000")  # result-callback audience
PUBSUB_TOPIC     = os.getenv("PUBSUB_TOPIC", "market-feed")
PUBSUB_SUB       = os.getenv("PUBSUB_SUB", "market-feed-sse")
TASKS_INVOKER_SA = os.getenv("TASKS_INVOKER_SA", "")

# --- Weave ---
WEAVE_PROJECT = os.getenv("WEAVE_PROJECT", "agent-bazaar")
WEAVE_DISABLED = os.getenv("WEAVE_DISABLED", "0") == "1"  # for offline tests

# --- Model exchange (AMM) constants (fixed; no tuning UI) ---
TIER_IPO_PRICE = {"pro": 20.0, "flash": 10.0, "lite": 5.0}
IPO_SHARES = 1000.0
EARN_RATE = float(os.getenv("EARN_RATE", "20.0"))   # credits per unit (score-0.5)*hire_weight
EARN_CLAMP = float(os.getenv("EARN_CLAMP", "200.0"))# max |earnings| per injection
MIN_POOL_SHARES = 1.0
MIN_POOL_CREDITS = 1.0

# --- Ledger constants ---
REP_ALPHA = float(os.getenv("REP_ALPHA", "0.3"))     # EMA factor
AWARD_RATE = float(os.getenv("AWARD_RATE", "1.0"))   # agent credit award scaler
UPGRADE_THRESHOLD = float(os.getenv("UPGRADE_THRESHOLD", "200.0"))

# --- Placeholder model price used before the exchange exists (Branch 2 only) ---
PLACEHOLDER_MODEL_PRICE = float(os.getenv("PLACEHOLDER_MODEL_PRICE", "10.0"))

# --- Users ---
USER_START_CREDITS = float(os.getenv("USER_START_CREDITS", "1000.0"))

# Redis keys (additions)
MODEL_PREFIX = "model:"
MODEL_PRICES_KEY = "model_prices"
PRICE_HISTORY_KEY = "price:history"
```

Keep the old `VERTEX_*` names for one branch only if any code still imports them; remove them in Branch 1 once `embeddings.py` is replaced. (Plan removes them in Branch 1.)

- [ ] **Add `.env.example`** at repo root documenting required keys (do not commit a real `.env`). Note `EMBED_BACKEND` is gone; **GCP credentials are now required even locally** because embeddings are GCP-only (set `GOOGLE_APPLICATION_CREDENTIALS` / ADC + `GCP_PROJECT`). Use `EMBEDDINGS_FAKE=1` for offline unit tests only:

```text
RUNTIME_ENV=local
DATABASE_URL=postgresql+asyncpg://bazaar:bazaar@localhost:5432/bazaar
REDIS_URL=redis://localhost:6379
GCP_PROJECT=                       # REQUIRED locally (embeddings are GCP-only)
GCP_LOCATION=us-central1
GCP_CHAT_MODEL=gemini-3.5-flash
GCP_EMBED_MODEL=gemini-embedding-001
# GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json   # or `gcloud auth application-default login`
OPENAI_API_KEY=
OPENAI_CHAT_MODEL=gpt-4.1-mini
WEAVE_PROJECT=agent-bazaar
WEAVE_DISABLED=1
EMBEDDINGS_FAKE=1                  # offline tests only; do NOT set in normal dev
```

- [ ] **Update `repo.py`** to stop referencing `price` and use `margin` (the upsert and `_to_schema` currently read `a.price`). Since the ORM column rename to `margin` happens in Branch 1, gate this: in Branch 0 only adjust the Pydantic-facing mapping to read `margin` with a temporary fallback, OR defer the repo edit to Branch 1 (recommended — keep Branch 0 contract-only). **Decision: defer repo `price`→`margin` to Branch 1** so Branch 0 stays green against the un-migrated DB. Document this in the branch PR.

### 0.2 New content

- [ ] **Define the ports (interfaces only, no adapters yet)** — new `backend/ports/` package. These are the local↔cloud seam; later branches consume them and Branch 7 adds GCP adapters. Define `Queue`, `EventBus`, `Embeddings` as `typing.Protocol`s plus a `RunDispatch` dataclass, and a `factory.py` switched by `RUNTIME_ENV`. Match the signatures in `docs/cloud-architecture.md` §3:

```python
# backend/ports/queue.py
from dataclasses import dataclass
from typing import Protocol

@dataclass
class RunDispatch:
    subtask_id: str; agent_id: str; service_url: str
    subtask_text: str; config: dict; task_id: str

class Queue(Protocol):
    async def enqueue_run(self, dispatch: RunDispatch) -> str: ...

# backend/ports/event_bus.py
from typing import AsyncIterator, Protocol
from contracts.events import MarketEvent
class EventBus(Protocol):
    async def publish(self, event: MarketEvent) -> None: ...
    def subscribe(self, *, from_id: str = "$") -> AsyncIterator[tuple[str, MarketEvent]]: ...

# backend/ports/embeddings.py
from typing import Protocol
import numpy as np
class Embeddings(Protocol):
    def embed(self, text: str) -> np.ndarray: ...        # float32, L2-normalized, len == VECTOR_DIM
    def embed_bytes(self, text: str) -> bytes: ...

# backend/ports/factory.py — get_queue()/get_event_bus()/get_embeddings(), @cache, lazy-import adapters by RUNTIME_ENV
```

Branch 0 ships **only the Protocols + factory + the local adapters' stubs** importing cleanly (adapters fleshed out in Branch 2). No Cloud SDK import at module top — GCP adapters lazy-import inside the factory branches. This keeps `feat/contracts-finalize` a contract-only branch while locking the seam shape everyone builds against.

- [ ] **Fill `contracts/CONTRACTS.md`** — the written spec. Sections, each a table copied/expanded from build_doc §3–4 so implementers have one source:
  1. **Event feed schema** — all 13 events (8 existing + 5 new) with payload fields; note `candidates_ranked.price` and `agent_hired` now reflect derived price.
  2. **API contract** — the full route table (existing 4 + new 8) with method, path, request body shape, response shape (reference the Pydantic models above).
  3. **Postgres tables** — the 8 tables with columns and types (matching Branch 1 migration).
  4. **Redis layout** — `agent:{id}`, `agents_idx`, `leaderboard`, `model:{id}`, `model_prices`, `market:feed`, `price:history` with field lists.
  5. **Derived pricing rule** — `price = model_price(model) * (1 + margin)`; where computed (broker rank, roster read).
  6. **AMM rule** — `price = C/S`, `k = S*C`, buy/sell/earnings formulas (copy from Branch 3).
  7. **Ports/adapters seam** — the `Queue`/`EventBus`/`Embeddings` interfaces, the `RUNTIME_ENV` flag, and the local vs GCP adapter for each (point to `docs/cloud-architecture.md` §3 rather than duplicating it).

- [ ] **Add `tests/test_contracts.py`** — pure unit tests (no DB/Redis) that round-trip every event and schema through Pydantic, proving the union discriminator and the new fields:

```python
from contracts.events import EVENT_ADAPTER, PriceChanged, TradeExecuted
from contracts.schemas import Agent, Model

def test_price_changed_roundtrip():
    ev = PriceChanged(model_id="gemini-3.5-flash", old=10.0, new=11.2, reason="earnings")
    parsed = EVENT_ADAPTER.validate_json(ev.model_dump_json())
    assert parsed.type == "price_changed" and parsed.new == 11.2

def test_agent_has_margin_not_required_price():
    a = Agent(agent_id="x", name="X", skills=[], capability_text="t", model="m")
    assert a.margin == 0.2 and a.price is None

def test_model_price_is_field():
    m = Model(model_id="m", name="M", provider="gcp", tier="flash",
              shares=1000.0, credits=10000.0, price=10.0, ipo_price=10.0)
    assert m.price == 10.0
```

### 0.3 Verification (Branch 0)

- [ ] `python -c "import contracts.events, contracts.schemas"` imports clean.
- [ ] `pytest tests/test_contracts.py -v` → all pass (no Postgres/Redis needed).
- [ ] `rg -n "mock_events|0001_init.py|from multiprocessing import Value|\.price" contracts backend tests` → no stale references except the deliberately-deferred repo `price` (documented).
- [ ] `python -m tests.smoke_test` is **not** expected to pass yet (DB not migrated for margin); it is verified at the end of Branch 1. Confirm only that the module path resolves: `python -c "import tests.smoke_test"`.

### 0.4 Dependency-ordered checklist (Branch 0)
1. Rename smoke test + add `tests/__init__.py`.
2. ORM `User.name`, remove dead import.
3. `contracts/schemas.py` margin + new models.
4. `contracts/events.py` new events + union.
5. `requirements.txt`, `config.py` (`RUNTIME_ENV`, drop `EMBED_BACKEND`), `.env.example`.
6. `backend/ports/` Protocols + `factory.py` (no Cloud SDK at import; local adapter stubs).
7. Remove `mock_events.json`.
8. Fill `CONTRACTS.md` (incl. the ports section).
9. `tests/test_contracts.py` (+ a trivial `import backend.ports.factory` smoke), run, commit.

---

## Branch 1 — `feat/persistence-exchange` (Phase 1: persistence & migrations)

**Base:** `feat/contracts-finalize`  ·  **Purpose:** evolve the schema to the build_doc §4.1 target (models/holdings/trades, user credits/is_sim, agent margin + model FK, drop price, ledger earnings), migrate embeddings to `google-genai`, and teach the seeder to list models and seed sim users.

### 1.1 Updates & cleanups

- [ ] **Replace `backend/infra/embeddings.py` with the GCP-only `Embeddings` adapter** — **remove the deterministic local-hash fallback entirely** (build_doc / `docs/cloud-architecture.md` §8). Implement `backend/adapters/gcp_embeddings.py` as the only runtime adapter, and `backend/adapters/fake_embeddings.py` for tests. Drop the `vertexai` imports and `VERTEX_*` config; remove the dead `from multiprocessing import Value`. The KNN-facing helpers (`embed_bytes`) now come from `get_embeddings()` (the factory). Implementation:

```python
# backend/adapters/gcp_embeddings.py
from google import genai
from google.genai import types
import numpy as np
from backend.config import GCP_PROJECT, GCP_LOCATION, GCP_EMBED_MODEL, VECTOR_DIM

class GcpEmbeddings:
    def __init__(self):
        self._c = genai.Client(vertexai=True, project=GCP_PROJECT, location=GCP_LOCATION)
    def embed(self, text: str) -> np.ndarray:
        resp = self._c.models.embed_content(
            model=GCP_EMBED_MODEL, contents=text,                       # "gemini-embedding-001"
            config=types.EmbedContentConfig(output_dimensionality=VECTOR_DIM,
                                            task_type="RETRIEVAL_DOCUMENT"))
        arr = np.asarray(resp.embeddings[0].values, dtype=np.float32)
        if arr.shape[0] != VECTOR_DIM:
            raise ValueError(f"{GCP_EMBED_MODEL} dim {arr.shape[0]} != VECTOR_DIM {VECTOR_DIM}; rebuild index")
        n = float(np.linalg.norm(arr))                                  # MANUAL L2 norm (required <3072 dims)
        return arr / n if n > 0 else arr
    def embed_bytes(self, text: str) -> bytes:
        return self.embed(text).tobytes()
```

`fake_embeddings.py` reuses the old deterministic feature-hash logic (now a *test* tool, not a runtime backend) so offline unit tests still get stable, dim-correct vectors. **Consequences (flag in the PR):** (1) local dev now needs GCP credentials for any embedding path — seeding and hiring will fail offline without them; (2) `VECTOR_DIM` must equal `output_dimensionality` (768) or the index mismatches; (3) embed the subtask *query* with `RETRIEVAL_QUERY` and the capability *text* with `RETRIEVAL_DOCUMENT`. **Verify `resp.embeddings[0].values` against the installed `google-genai` 2.8** with a 5-line spike before wiring (still the top SDK risk — see Open Decisions).

- [ ] **Update `backend/db/models.py`** for the schema delta.

`User` — add credits + is_sim:
```python
    credits: Mapped[float] = mapped_column(Numeric(14, 2), default=0.0)
    is_sim: Mapped[bool] = mapped_column(Boolean, default=False)
```

`Agent` — drop `price`, add `margin`, make `model` a FK to `models.model_id`:
```python
    model: Mapped[str] = mapped_column(String(128), ForeignKey("models.model_id"))
    margin: Mapped[float] = mapped_column(Numeric(6, 4), default=0.2)
    # (remove the `price` column entirely)
```

`LedgerEntry` — allow `kind="earnings"` (already `String(20)`, no DDL needed) and add nullable `model_id` so earnings rows point at the stock they fed:
```python
    model_id: Mapped[str | None] = mapped_column(ForeignKey("models.model_id"), nullable=True)
    amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)  # earnings amount
```

Add imports: `Boolean` from sqlalchemy.

- [ ] **Update `backend/db/repo.py`** — `_to_schema` and `upsert_agent` use `margin` instead of `price`; `create_user` accepts `credits`/`is_sim`:

```python
def _to_schema(a: Agent) -> AgentSchema:
    return AgentSchema(
        agent_id=a.agent_id, name=a.name, skills=list(a.skills or []),
        capability_text=a.capability_text, model=a.model, tools=list(a.tools or []),
        reputation=float(a.reputation), credits=float(a.credits),
        margin=float(a.margin), hires=a.hires, wins=a.wins, service_url=a.service_url,
    )

async def create_user(session, email, name, *, credits=0.0, is_sim=False, password_hash=None) -> User:
    user = User(email=email, name=name, credits=credits, is_sim=is_sim, password_hash=password_hash)
    session.add(user); await session.flush(); return user
```

In `upsert_agent`, replace `price=agent.price` with `margin=agent.margin`.

- [ ] **Update `backend/market/registry.py`** — the pure serializers carry `margin`, not `price`:
  - `agent_to_mapping`: replace `"price": str(agent.price)` with `"margin": str(agent.margin)`.
  - `mapping_to_agent`: replace `price=float(d["price"])` with `margin=float(d["margin"])`.
  - Add **model projection helpers** here (see New content 1.2).

- [ ] **Update `backend/market/seed_agents.py`** — drop the `price=` kwargs, add `margin=` (spread so derived prices differ), keep models pointing at distinct tiers. Example diff for one entry:
```python
    Agent(agent_id="writer-01", name="Copywriter", skills=["writing","summarization"],
          capability_text="Writes and summarizes marketing and technical copy ...",
          model="gemini-3.5-flash", tools=[], margin=0.20,
          service_url="http://localhost:9001"),
```
Set margins ~0.10–0.35 across the six. Also normalize model ids to those the exchange will list (see seeder).

- [ ] **Update `tests/smoke_test.py`** — no `price` reads; it already only prints reputation/match. Confirm `seed()` still returns count after model listing is added.

### 1.2 New content

- [ ] **Alembic revision `0002_exchange`** (`alembic/versions/0002_exchange.py`). Create it with `alembic revision -m "exchange: models, holdings, trades; user credits; agent margin"` then hand-write the body (do not rely solely on autogenerate; verify it matches). Exact operations:

```python
revision = "0002_exchange"
down_revision = "0001_init"

def upgrade() -> None:
    # 1. models (must exist before agents.model FK)
    op.create_table(
        "models",
        sa.Column("model_id", sa.String(length=128), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),   # gcp | openai
        sa.Column("tier", sa.String(length=16), nullable=False),       # pro | flash | lite
        sa.Column("executable", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("pool_shares", sa.Numeric(18, 6), nullable=False),
        sa.Column("pool_credits", sa.Numeric(18, 6), nullable=False),
        sa.Column("ipo_price", sa.Numeric(12, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    # 2. users: credits + is_sim
    op.add_column("users", sa.Column("credits", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")))
    op.add_column("users", sa.Column("is_sim", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    # 3. agents: add margin, drop price, add FK agents.model -> models.model_id
    op.add_column("agents", sa.Column("margin", sa.Numeric(6, 4), nullable=False, server_default=sa.text("0.2")))
    op.drop_column("agents", "price")
    op.create_foreign_key("fk_agents_model", "agents", "models", ["model"], ["model_id"])
    # (optional) align agents.name length 200 -> 255 to match ORM
    op.alter_column("agents", "name", type_=sa.String(length=255))
    # 4. holdings
    op.create_table(
        "holdings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("model_id", sa.String(length=128), sa.ForeignKey("models.model_id"), nullable=False),
        sa.Column("shares", sa.Numeric(18, 6), nullable=False, server_default=sa.text("0")),
    )
    op.create_unique_constraint("uq_holdings_user_model", "holdings", ["user_id", "model_id"])
    # 5. trades
    op.create_table(
        "trades",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("model_id", sa.String(length=128), sa.ForeignKey("models.model_id"), nullable=False),
        sa.Column("side", sa.String(length=4), nullable=False),     # buy | sell
        sa.Column("shares", sa.Numeric(18, 6), nullable=False),
        sa.Column("credits", sa.Numeric(18, 6), nullable=False),
        sa.Column("price", sa.Numeric(12, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    # 6. ledger: model_id + amount for earnings rows
    op.add_column("ledger_entries", sa.Column("model_id", sa.String(length=128), sa.ForeignKey("models.model_id"), nullable=True))
    op.add_column("ledger_entries", sa.Column("amount", sa.Numeric(14, 2), nullable=True))

def downgrade() -> None:
    op.drop_column("ledger_entries", "amount")
    op.drop_column("ledger_entries", "model_id")
    op.drop_table("trades")
    op.drop_constraint("uq_holdings_user_model", "holdings", type_="unique")
    op.drop_table("holdings")
    op.alter_column("agents", "name", type_=sa.String(length=200))
    op.drop_constraint("fk_agents_model", "agents", type_="foreignkey")
    op.add_column("agents", sa.Column("price", sa.Numeric(10, 2), nullable=False, server_default=sa.text("5.0")))
    op.drop_column("agents", "margin")
    op.drop_column("users", "is_sim")
    op.drop_column("users", "credits")
    op.drop_table("models")
```

Note the **ordering constraint**: `models` is created before the `agents.model` FK is added, and dropped last on downgrade. Keep the migration filename revision id `0002_exchange` aligned with the existing `0001_init` style (filename matches `down_revision` chain). No need to rename `0001_init.py`.

- [ ] **New ORM models** in `backend/db/models.py` (`Model`, `Holding`, `Trade`):

```python
class Model(Base):
    __tablename__ = "models"
    model_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    provider: Mapped[str] = mapped_column(String(16))   # gcp | openai
    tier: Mapped[str] = mapped_column(String(16))       # pro | flash | lite
    executable: Mapped[bool] = mapped_column(Boolean, default=True)
    pool_shares: Mapped[float] = mapped_column(Numeric(18, 6))
    pool_credits: Mapped[float] = mapped_column(Numeric(18, 6))
    ipo_price: Mapped[float] = mapped_column(Numeric(12, 4))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Repo helpers** in `backend/db/repo.py` for the new tables (Postgres truth; AMM mutation logic lives in the exchange module in Branch 3, but the basic CRUD lives here):

```python
async def upsert_model(session, *, model_id, name, provider, tier, shares, credits, ipo_price, executable=True): ...
async def get_model(session, model_id) -> Model | None: ...
async def list_models(session) -> list[Model]: ...
async def update_model_pool(session, model_id, *, shares, credits) -> None: ...  # writes pool_shares/credits
async def get_holding(session, user_id, model_id) -> Holding | None: ...
async def upsert_holding(session, user_id, model_id, shares) -> None: ...
async def list_holdings(session, user_id) -> list[Holding]: ...
async def record_trade(session, *, user_id, model_id, side, shares, credits, price) -> Trade: ...
async def adjust_user_credits(session, user_id, delta) -> float: ...  # returns new balance
async def list_users(session) -> list[User]: ...
```

`clear_market` must also wipe models/holdings/trades (FK-safe order): `LedgerEntry → Subtask → Task → Trade → Holding → Agent → Model`. Leave `users` rows but optionally reset sim users (the seeder recreates them).

- [ ] **Redis model projection** in `backend/market/registry.py`:

```python
def model_key(model_id: str) -> str:
    return f"{MODEL_PREFIX}{model_id}"

async def project_model(r, m) -> None:
    """Write model:{id} hash and set its model_prices score to current price."""
    price = float(m.pool_credits) / float(m.pool_shares)
    await r.hset(model_key(m.model_id), mapping={
        "model_id": m.model_id, "name": m.name, "provider": m.provider, "tier": m.tier,
        "executable": "1" if m.executable else "0",
        "shares": str(float(m.pool_shares)), "credits": str(float(m.pool_credits)),
        "price": str(price), "ipo_price": str(float(m.ipo_price)),
    })
    await r.zadd(MODEL_PRICES_KEY, {m.model_id: price})

async def get_model_cached(r, model_id) -> dict | None:
    mapping = await r.hgetall(model_key(model_id))
    return {to_str(k): to_str(v) for k, v in mapping.items()} if mapping else None

async def get_model_price(r, model_id) -> float | None:
    p = await r.hget(model_key(model_id), "price")
    return float(to_str(p)) if p is not None else None

async def list_models_cached(r) -> list[dict]: ...  # scan model:* and decode
```

Extend `reset_redis` to also delete `model:*`, `MODEL_PRICES_KEY`, and `PRICE_HISTORY_KEY`.

- [ ] **Seeder: list models and seed sim users** (`backend/market/seeder.py`). Add a `SEED_MODELS` table in a new `backend/market/seed_models.py`:

```python
# backend/market/seed_models.py
SEED_MODELS = [
    {"model_id": "gemini-3.1-pro-preview",        "name": "Gemini 3.1 Pro",   "provider": "gcp",    "tier": "pro"},
    {"model_id": "gemini-3.5-flash",              "name": "Gemini 3.5 Flash", "provider": "gcp",    "tier": "flash"},
    {"model_id": "gemini-3.1-flash-lite-preview", "name": "Gemini Flash Lite","provider": "gcp",    "tier": "lite"},
    {"model_id": "gemma-4-26b-a4b-it",            "name": "Gemma 4 26B",      "provider": "gcp",    "tier": "lite"},
    {"model_id": "gpt-4.1-mini",                  "name": "GPT-4.1 Mini",     "provider": "openai", "tier": "flash"},
    {"model_id": "gpt-4.1",                       "name": "GPT-4.1",          "provider": "openai", "tier": "pro"},
]
```

Every `model` referenced by a seed agent **must** appear here (the FK requires it). In `seed()`:
1. Clear market (Postgres) + reset Redis.
2. **List models first** (Postgres `upsert_model` with IPO pool: `shares=IPO_SHARES`, `price0=TIER_IPO_PRICE[tier]`, `credits=price0*shares`, `ipo_price=price0`), then `registry.project_model`. Emit `ModelListed` per model (import `emit`).
3. Upsert seed agents (FK now satisfied), project to Redis.
4. **Seed sim users:** create N sim task-posters and M sim investors via `repo.create_user(..., credits=USER_START_CREDITS, is_sim=True)`. Names like `sim-poster-1`, `sim-investor-1`.
5. Return counts `{agents, models, users}`.

Add a small `list_model(...)` helper or inline the IPO math here; the full AMM module (Branch 3) will own listing going forward, but the seeder can call `exchange.list_model` once that exists — for Branch 1, inline IPO pool creation in the seeder and refactor to call `exchange.list_model` in Branch 3.

### 1.3 Verification (Branch 1)

- [ ] `docker compose up -d postgres redis`
- [ ] `alembic upgrade head` → reaches `0002_exchange` with no error; `alembic downgrade -1 && alembic upgrade head` round-trips cleanly (proves the migration is reversible).
- [ ] `python -m backend.market.seeder` prints seeded agents + models + users; no FK violation.
- [ ] `python -m tests.smoke_test` passes (seed, list agents, KNN, leaderboard, emit/read).
- [ ] New: `tests/test_seed_models.py` asserts every `seed_agents` model id ∈ `SEED_MODELS` ids (catches FK breakage before hitting the DB):
```python
from backend.market.seed_agents import SEED_AGENTS
from backend.market.seed_models import SEED_MODELS
def test_every_agent_model_is_listed():
    listed = {m["model_id"] for m in SEED_MODELS}
    assert {a.model for a in SEED_AGENTS} <= listed
```
- [ ] `redis-cli ZRANGE model_prices 0 -1 WITHSCORES` shows all models at tier IPO prices.

### 1.4 Dependency-ordered checklist (Branch 1)
1. `adapters/gcp_embeddings.py` (+ `fake_embeddings.py`); delete `infra/embeddings.py` local-hash path; remove `VERTEX_*` from config; factory returns `GcpEmbeddings` (or `FakeEmbeddings` when `EMBEDDINGS_FAKE=1`).
2. ORM: User credits/is_sim; Agent margin/FK/drop price; new Model/Holding/Trade; LedgerEntry model_id/amount.
3. `repo.py` margin + new-table helpers + clear_market order.
4. Alembic `0002_exchange`; test upgrade/downgrade.
5. `registry.py` model projection + reset_redis.
6. `seed_models.py`; seeder lists models + sim users.
7. `seed_agents.py` margins.
8. Tests, run, commit.

---

## Branch 2 — `feat/agent-loop` (Phase 2: the core agent loop)

**Base:** `feat/persistence-exchange`  ·  **Purpose:** make one task run end-to-end and get scored, using a **placeholder fixed model price** so the loop exists before the exchange. Build the agent base service + model router, the seed agent services, the judge, the broker, the FastAPI app with the first four routes, and Weave on every LLM call.

### 2.1 Updates & cleanups

- [ ] **Flesh out the LOCAL adapters** behind the ports defined in Branch 0 (`backend/adapters/`). These are what make the loop run on a laptop; the GCP adapters come in Branch 7.
  - `local_event_bus.py` — `LocalEventBus.publish(event)` = `feed.emit(r, event)` (XADD `market:feed`); `subscribe(from_id)` = the `feed.read_new` XREAD loop. The Redis Stream is the replay log.
  - `local_queue.py` — `LocalQueue.enqueue_run(dispatch)`: open its own redis/session scope, `await httpx.post(f"{dispatch.service_url}/run", json={"subtask_text":..., "config":...})`, read `{"output":...}`, then call `broker.handle_run_result(r, session, subtask_id=..., agent_id=..., output=..., task_id=...)`. Run it via `asyncio.create_task` so `/task` returns immediately (own scope — do not reuse the request session). Returns a synthetic dispatch id.
  - Confirm `factory.get_queue()/get_event_bus()` return these when `RUNTIME_ENV=local` (default). The broker/api import only the factory, never the adapters.

- [ ] **Add a Weave bootstrap** so `weave.init` runs exactly once per process. New `backend/infra/weave_init.py`:
```python
import weave
from backend.config import WEAVE_PROJECT, WEAVE_DISABLED
_inited = False
def init_weave() -> None:
    global _inited
    if _inited or WEAVE_DISABLED:
        return
    weave.init(WEAVE_PROJECT)
    _inited = True
```
Call `init_weave()` in the FastAPI lifespan and at the top of each agent service `main`. When `WEAVE_DISABLED=1` (tests/offline), `@weave.op` still works (it is a no-op-friendly decorator) but no network init happens.

- [ ] **Model router** — the single place that maps a model id to a provider client. New `backend/infra/model_router.py`:
```python
from backend.infra.weave_init import init_weave
import weave

@weave.op
def generate(model: str, provider: str, prompt: str, system: str | None = None) -> str:
    if provider == "openai":
        return _openai_generate(model, prompt, system)
    return _gcp_generate(model, prompt, system)

def _gcp_generate(model, prompt, system):
    from google import genai
    from backend.config import GCP_PROJECT, GCP_LOCATION
    client = genai.Client(vertexai=True, project=GCP_PROJECT, location=GCP_LOCATION)
    contents = (system + "\n\n" + prompt) if system else prompt
    return client.models.generate_content(model=model, contents=contents).text

def _openai_generate(model, prompt, system):
    from openai import OpenAI
    oai = OpenAI()  # OPENAI_API_KEY
    inp = (system + "\n\n" + prompt) if system else prompt
    return oai.responses.create(model=model, input=inp).output_text
```
Provider is looked up from the model row (`models.provider`) — the broker passes `config` containing `model`, `provider`, `system`, `tools` to the agent, so the agent never hard-codes a provider.

### 2.2 New content

- [ ] **Agent base service** — `backend/agent/base.py` (the FastAPI wrapper every agent honors). One image, parameterized by env (`AGENT_ID`, `AGENT_SYSTEM_PROMPT`, port). Contract: `POST /run {subtask_text, config}` → `{output}`:
```python
# config shape passed by the broker:
# {"model": "gemini-3.5-flash", "provider": "gcp", "system": "...", "tools": []}
from fastapi import FastAPI
from pydantic import BaseModel
from backend.infra.weave_init import init_weave
from backend.infra.model_router import generate
import weave

class RunConfig(BaseModel):
    model: str
    provider: str
    system: str | None = None
    tools: list[str] = []

class RunRequest(BaseModel):
    subtask_text: str
    config: RunConfig

def build_app(agent_id: str) -> FastAPI:
    init_weave()
    app = FastAPI(title=f"agent:{agent_id}")

    @weave.op
    def execute(subtask_text: str, config: RunConfig) -> str:
        return generate(config.model, config.provider, subtask_text, config.system)

    @app.post("/run")
    async def run(req: RunRequest):
        return {"output": execute(req.subtask_text, req.config)}

    @app.get("/healthz")
    async def healthz(): return {"ok": True, "agent_id": agent_id}
    return app
```

- [ ] **Agent entrypoint** — `backend/agent/main.py`: reads `AGENT_ID` + port from env, `app = build_app(os.environ["AGENT_ID"])`, run with uvicorn. Document running all six locally on ports 9001–9006 (matches `seed_agents.service_url`). A helper script `scripts/run_agents.sh` launches them.

- [ ] **Judge** — `backend/market/judge.py` (single GCP call, forced JSON, Weave traced):
```python
import json, weave
from backend.infra.model_router import generate
from backend.config import GCP_CHAT_MODEL

@weave.op
def judge(subtask_text: str, output: str) -> tuple[float, str]:
    prompt = (
        "Score how well OUTPUT satisfies TASK from 0.0 to 1.0. "
        'Reply ONLY JSON: {"score": <float>, "reason": "<one line>"}.\n\n'
        f"TASK:\n{subtask_text}\n\nOUTPUT:\n{output}\n"
    )
    raw = generate(GCP_CHAT_MODEL, "gcp", prompt)
    try:
        data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
        return max(0.0, min(1.0, float(data["score"]))), str(data.get("reason", ""))
    except Exception:
        return 0.5, "judge parse fallback"
```

- [ ] **Derived pricing helper** — `backend/market/pricing.py`. Branch 2 uses the placeholder; Branch 3 swaps the body to read Redis:
```python
from backend.config import PLACEHOLDER_MODEL_PRICE
async def model_price(r, model_id: str) -> float:
    return PLACEHOLDER_MODEL_PRICE   # Branch 3: return await registry.get_model_price(r, model_id)

def derived_price(model_price_value: float, margin: float) -> float:
    return model_price_value * (1.0 + margin)
```

- [ ] **Broker** — `backend/market/broker.py` (decompose → match → rank → **dispatch via `Queue`** → result → judge). Events go through the **`EventBus`** port; embeddings through the **`Embeddings`** port. All LLM steps Weave-traced. The broker **does not await the model output**; output returns via the shared `handle_run_result` (called directly by `LocalQueue`, or by the cloud result callback).
```python
import weave
from contracts.schemas import Candidate, Subtask
from contracts.events import (TaskPosted, CandidatesRanked, AgentHired, TaskExecuted, TaskScored)
from backend.config import W_MATCH, W_REP, W_PRICE, GCP_CHAT_MODEL
from backend.ports.factory import get_event_bus, get_embeddings   # Queue obtained per-dispatch
from backend.ports.queue import RunDispatch
from backend.market import registry, pricing
from backend.market.judge import judge

bus = get_event_bus(); emb = get_embeddings()

@weave.op
def decompose(goal: str) -> list[str]:
    prompt = ('Split GOAL into 1-4 ordered subtasks. Reply ONLY JSON list of strings.\n\n'
              f"GOAL: {goal}")
    raw = generate(GCP_CHAT_MODEL, "gcp", prompt)  # parse JSON list, fallback [goal]
    ...

@weave.op
async def rank(r, subtask_text: str, k: int = 5) -> list[Candidate]:
    hits = await registry.search(r, emb.embed_bytes(subtask_text), k=k)  # [(agent_id, match)] (RETRIEVAL_QUERY)
    out = []
    for agent_id, match in hits:
        a = await registry.get_agent_cached(r, agent_id)
        mp = await pricing.model_price(r, a.model)
        price = pricing.derived_price(mp, a.margin)
        final = W_MATCH*match + W_REP*a.reputation - W_PRICE*price
        out.append(Candidate(agent_id=agent_id, match_score=match,
                             reputation=a.reputation, price=price, final_score=final))
    out.sort(key=lambda c: c.final_score, reverse=True)
    return out

async def run_task(r, session, task_id: str, goal: str) -> None:
    queue = get_queue()
    subtask_texts = decompose(goal)
    subtasks = [Subtask(subtask_id=f"{task_id}-{i}", text=t) for i, t in enumerate(subtask_texts)]
    await bus.publish(TaskPosted(task_id=task_id, goal=goal, subtasks=subtasks))
    for st in subtasks:
        cands = await rank(r, st.text)
        await bus.publish(CandidatesRanked(subtask_id=st.subtask_id, candidates=cands))
        top = cands[0]
        await bus.publish(AgentHired(subtask_id=st.subtask_id, agent_id=top.agent_id))
        a = await registry.get_agent_cached(r, top.agent_id)
        model = await registry.get_model_cached(r, a.model)
        config = {"model": a.model, "provider": model["provider"],
                  "system": SYSTEM_PROMPTS.get(top.agent_id), "tools": a.tools}
        # Dispatch through the Queue port (LocalQueue: in-proc HTTP + calls handle_run_result;
        # GcpTasksQueue (Branch 7): Cloud Tasks push, result returns via the OIDC callback).
        await queue.enqueue_run(RunDispatch(
            subtask_id=st.subtask_id, agent_id=top.agent_id, service_url=a.service_url,
            subtask_text=st.text, config=config, task_id=task_id))

async def handle_run_result(r, session, *, subtask_id, agent_id, output, task_id) -> None:
    """Shared continuation after an agent runs. IDEMPOTENT on subtask_id (a Cloud Tasks
    retry can deliver a second result). Called directly by LocalQueue, or by the API's
    /internal/runs/result route in cloud."""
    if await registry.subtask_already_scored(r, subtask_id):   # idempotency guard
        return
    await bus.publish(TaskExecuted(subtask_id=subtask_id, agent_id=agent_id, output_preview=output[:280]))
    score, _reason = judge(_subtask_text_for(subtask_id), output)
    await bus.publish(TaskScored(subtask_id=subtask_id, agent_id=agent_id, judge_score=score))
    # Branch 3: ledger.settle(...) here.
```
`SYSTEM_PROMPTS` comes from `seed_agents.SUGGESTED_PROMPTS` (move/import it). Persist subtasks + scores to Postgres via repo (add `repo.save_subtask_result`); the persisted subtask row also carries the text so `handle_run_result` can fetch it (replace `_subtask_text_for` with a repo read). The idempotency guard can be a Redis `SETNX scored:{subtask_id}` or a check that the subtask row already has a `judge_score`.

- [ ] **FastAPI app** — fill `backend/api/__init__.py` (or a new `backend/api/app.py` and keep `__init__` re-exporting). Routes for Phase 2:
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from sse_starlette.sse import EventSourceResponse
from backend.infra.weave_init import init_weave
from backend.infra.redis_client import get_redis, close_redis
from backend.infra.db import get_session, session_scope
from backend.market import registry, broker, seeder, pricing
from backend.ports.factory import get_event_bus

@asynccontextmanager
async def lifespan(app):
    init_weave(); yield; await close_redis()

app = FastAPI(title="Agent Bazaar API", lifespan=lifespan)
bus = get_event_bus()

@app.get("/agents")            # roster w/ derived price
async def get_agents(session=Depends(get_session)):
    r = get_redis(); out = []
    for a in await repo.list_agents(session):
        mp = await pricing.model_price(r, a.model)
        a.price = pricing.derived_price(mp, a.margin)
        out.append(a.model_dump(exclude={"service_url"}))
    return out

@app.post("/task")             # {goal, user_id?} -> {task_id}
async def post_task(body: dict, session=Depends(get_session)):
    r = get_redis()
    task = await repo.create_task(session, goal=body["goal"], user_id=body.get("user_id"))
    asyncio.create_task(_run(str(task.id), body["goal"]))  # background; see note
    return {"task_id": str(task.id)}

@app.get("/feed")              # SSE — consumes the EventBus port (Redis Stream local; Pub/Sub in cloud)
async def feed_sse():
    async def gen():
        async for _cursor, ev in bus.subscribe(from_id="$"):
            yield {"event": ev.type, "data": ev.model_dump_json()}
    return EventSourceResponse(gen())

@app.post("/seed")             # reset both markets
async def post_seed():
    counts = await seeder.seed(); return {"ok": True, **counts}
```
**Cloud-mode result callback (route added now, used in Branch 7):** add an internal route so the cloud `Queue` adapter's agents can return their output:
```python
@app.post("/internal/runs/result")   # in cloud: protected by OIDC (run.invoker); local: unused
async def run_result(body: dict, session=Depends(get_session)):
    r = get_redis()
    await broker.handle_run_result(r, session, subtask_id=body["subtask_id"],
                                   agent_id=body["agent_id"], output=body["output"],
                                   task_id=body["task_id"])
    return {"ok": True}
```
**Background execution note:** `asyncio.create_task` inside a request needs its own session/redis scope (don't reuse the request session). `broker.run_task` only *dispatches* (it no longer awaits the model), so `/task` returns immediately; the `LocalQueue` adapter owns the background HTTP call + `handle_run_result`. Open the background scope inside the adapter, not the request handler. If it proves flaky under the sim's load, fall back to awaiting the local dispatch synchronously — call this out as an open decision.

- [ ] **Add repo task helpers:** `create_task`, `save_subtask_result(session, task_id, order_index, text, agent_id, output_preview, judge_score)`, and a `get_subtask(session, subtask_id)` so `handle_run_result` can read the subtask text (replaces the `_subtask_text_for` placeholder).

- [ ] **docker-compose:** add an `api` service (reuse the image, command `uvicorn backend.api:app --host 0.0.0.0 --port 8000`, depends on postgres+redis, env `RUNTIME_ENV=local`, DATABASE_URL/REDIS_URL + GCP/OpenAI keys; mount/inject GCP creds for embeddings). Agents run on localhost in dev (not containerized this pass).

### 2.3 Verification (Branch 2)

- [ ] Offline unit test (no cloud): `tests/test_broker_rank.py` monkeypatches `registry.search` and `get_agent_cached` to assert `final_score = w_match*match + w_rep*rep - w_price*price` and that candidates sort descending. `WEAVE_DISABLED=1`.
- [ ] Live loop (real models): `docker compose up -d postgres redis`, `alembic upgrade head`, `python -m backend.market.seeder`, launch the six agents (`scripts/run_agents.sh`), `uvicorn backend.api:app`. Then:
  - `curl -X POST :8000/seed`
  - `curl -X POST :8000/task -d '{"goal":"Write a launch blog post and a tagline"}'`
  - `curl -N :8000/feed` shows `task_posted → candidates_ranked → agent_hired → task_executed → task_scored`.
- [ ] Weave UI shows traced ops: `decompose`, `rank`, agent `execute`, `judge`, `generate`.
- [ ] `curl :8000/agents` shows derived `price` = `PLACEHOLDER_MODEL_PRICE * (1+margin)`.

### 2.4 Dependency-ordered checklist (Branch 2)
1. `adapters/local_event_bus.py`, `adapters/local_queue.py` (flesh out the Branch 0 stubs).
2. `weave_init.py`, `model_router.py`.
3. `agent/base.py`, `agent/main.py`, `scripts/run_agents.sh`.
4. `judge.py`, `pricing.py` (placeholder).
5. `broker.py` (dispatch via `Queue` port + `handle_run_result`) + repo task/subtask helpers.
6. `api/__init__.py` routes (incl. `/internal/runs/result`) + lifespan via `EventBus`; compose `api` service.
7. Tests (offline rank, with `EMBEDDINGS_FAKE=1`), then live loop, commit.

---

## Branch 3 — `feat/ledger-exchange` (Phase 3: ledger + the AMM)

**Base:** `feat/agent-loop`  ·  **Purpose:** turn judge scores into reputation/credits and **earnings injected into the model stock**, build the constant-product AMM (list/buy/sell/inject), and switch the broker's derived price to the live model price. After this branch, tasks move reputation/credits and model prices move on earnings.

### 3.1 Updates & cleanups

- [ ] **Switch `pricing.model_price` to live reads** (`backend/market/pricing.py`):
```python
from backend.market import registry
async def model_price(r, model_id: str) -> float:
    p = await registry.get_model_price(r, model_id)
    return p if p is not None else PLACEHOLDER_MODEL_PRICE  # fallback if not projected
```
No broker change needed — it already calls `pricing.model_price`. This is the build_doc §4.4 promise: the exchange moving reprices hires with zero broker edits.

- [ ] **Wire the broker to the ledger.** In `broker.handle_run_result` (where the `# Branch 3` comment is, after `TaskScored`), look up the agent + its derived price and call:
```python
from backend.market.ledger import settle
a = await registry.get_agent_cached(r, agent_id)
mp = await pricing.model_price(r, a.model)
await settle(r, session, agent_id=agent_id, model_id=a.model,
             judge_score=score, derived_price=pricing.derived_price(mp, a.margin), task_id=task_id)
```
(Settling happens in the shared result handler so it runs identically whether the output came back via the local in-proc dispatch or the cloud Cloud Tasks callback.)

- [ ] **Refactor the seeder** to list models through `exchange.list_model` instead of inline IPO math, so listing has one owner. Keep behavior identical.

### 3.2 New content

- [ ] **Model Exchange (AMM)** — `backend/market/exchange.py`. Constant product `price = C/S`, `k = S*C`. Every mutation writes Postgres (truth) + Redis (projection) and emits events. Edge cases per build_doc §9. Weave-traced.

```python
import weave
from backend.config import (TIER_IPO_PRICE, IPO_SHARES, EARN_RATE, EARN_CLAMP,
                            MIN_POOL_SHARES, MIN_POOL_CREDITS, PRICE_HISTORY_KEY)
from backend.db import repo
from backend.market import registry
from backend.ports.factory import get_event_bus
bus = get_event_bus()   # emit(r, X) below is shorthand for bus.publish(X); feed.emit lives only in LocalEventBus
from contracts.events import ModelListed, PriceChanged, EarningsInjected, TradeExecuted

async def list_model(session, r, *, model_id, name, provider, tier, executable=True):
    price0 = TIER_IPO_PRICE[tier]
    shares, credits = IPO_SHARES, price0 * IPO_SHARES
    m = await repo.upsert_model(session, model_id=model_id, name=name, provider=provider,
                                tier=tier, shares=shares, credits=credits,
                                ipo_price=price0, executable=executable)
    await registry.project_model(r, m)
    await emit(r, ModelListed(model_id=model_id, name=name, provider=provider, tier=tier, ipo_price=price0))
    return m

def _price(shares, credits): return credits / shares

@weave.op
async def buy(session, r, *, model_id, dc) -> tuple[float, float]:
    """Spend dc credits, return (shares_out, new_price). Reject empty/zero."""
    m = await repo.get_model(session, model_id)
    if m is None or dc <= 0: raise ValueError("bad buy")
    S, C = float(m.pool_shares), float(m.pool_credits)
    k = S * C
    old = _price(S, C)
    C2 = C + dc
    S2 = max(MIN_POOL_SHARES, k / C2)   # never empty the share side
    shares_out = S - S2
    if shares_out <= 0: raise ValueError("trade too small / pool floor hit")
    await _commit_pool(session, r, model_id, S2, C2, old, reason="trade")
    return shares_out, _price(S2, C2)

@weave.op
async def sell(session, r, *, model_id, ds) -> tuple[float, float]:
    """Return ds shares, return (credits_out, new_price). Reject empty/zero."""
    m = await repo.get_model(session, model_id)
    if m is None or ds <= 0: raise ValueError("bad sell")
    S, C = float(m.pool_shares), float(m.pool_credits)
    k = S * C
    old = _price(S, C)
    S2 = S + ds
    C2 = max(MIN_POOL_CREDITS, k / S2)
    credits_out = C - C2
    if credits_out <= 0: raise ValueError("trade too small / pool floor hit")
    await _commit_pool(session, r, model_id, S2, C2, old, reason="trade")
    return credits_out, _price(S2, C2)

@weave.op
async def inject_earnings(session, r, *, model_id, agent_id, amount, judge_score):
    """Fundamentals: add `amount` credits to the pool WITHOUT issuing shares.
    Recompute k implicitly (k = S*C2). Positive lifts price, negative bleeds it."""
    m = await repo.get_model(session, model_id)
    if m is None: return
    S, C = float(m.pool_shares), float(m.pool_credits)
    old = _price(S, C)
    amount = max(-EARN_CLAMP, min(EARN_CLAMP, amount))      # clamp
    C2 = max(MIN_POOL_CREDITS, C + amount)                   # floor pool
    await _commit_pool(session, r, model_id, S, C2, old, reason="earnings")
    await emit(r, EarningsInjected(model_id=model_id, agent_id=agent_id,
                                   amount=amount, judge_score=judge_score))

async def _commit_pool(session, r, model_id, S2, C2, old_price, *, reason):
    await repo.update_model_pool(session, model_id, shares=S2, credits=C2)
    m = await repo.get_model(session, model_id)
    await registry.project_model(r, m)                       # updates model:{id} + model_prices
    new = _price(S2, C2)
    await emit(r, PriceChanged(model_id=model_id, old=old_price, new=new, reason=reason))
    await r.xadd(PRICE_HISTORY_KEY, {"model_id": model_id, "price": str(new)})  # optional chart
```

**AMM edge-case rules (build_doc §9):** floor `shares ≥ MIN_POOL_SHARES` and `credits ≥ MIN_POOL_CREDITS`; reject trades that don't yield positive output (too small or would empty a pool); clamp earnings to `±EARN_CLAMP`. `inject_earnings` adds to `C` only (no shares minted) so existing holders' value rises — that is the fundamentals signal.

- [ ] **Ledger** — `backend/market/ledger.py` (reputation EMA, credits award, earnings handoff, ledger rows, leaderboard, Weave-traced):
```python
import weave
from backend.config import REP_ALPHA, AWARD_RATE, EARN_RATE
from backend.db import repo
from backend.market import registry, exchange
from backend.ports.factory import get_event_bus
bus = get_event_bus()   # emit(r, X) below is shorthand for bus.publish(X); feed.emit lives only in LocalEventBus
from contracts.events import ReputationChanged, CreditsChanged

@weave.op
async def settle(r, session, *, agent_id, model_id, judge_score, derived_price, task_id):
    a = await repo.get_agent(session, agent_id)            # current truth
    old_rep = a.reputation
    new_rep = REP_ALPHA * judge_score + (1 - REP_ALPHA) * old_rep
    award = AWARD_RATE * judge_score * derived_price        # earned its fee
    old_cred = a.credits
    new_cred = old_cred + award
    await repo.update_agent_stats(session, agent_id, reputation=new_rep, credits=new_cred,
                                  inc_hires=1, inc_wins=1 if judge_score >= 0.5 else 0)
    # reproject agent hash + leaderboard
    await registry.update_leaderboard(r, agent_id, new_rep)
    await registry.reproject_agent(r, session, agent_id)   # refresh hash fields
    await emit(r, ReputationChanged(agent_id=agent_id, old=old_rep, new=new_rep))
    await emit(r, CreditsChanged(agent_id=agent_id, old=old_cred, new=new_cred))
    await repo.add_ledger_entry(session, agent_id=agent_id, task_id=task_id, kind="award",
                                credits_delta=award, reputation_before=old_rep, reputation_after=new_rep)
    # earnings into the model stock (fundamentals)
    hire_weight = 1.0
    earnings = EARN_RATE * (judge_score - 0.5) * hire_weight
    await exchange.inject_earnings(session, r, model_id=model_id, agent_id=agent_id,
                                   amount=earnings, judge_score=judge_score)
    await repo.add_ledger_entry(session, agent_id=agent_id, task_id=task_id, kind="earnings",
                                credits_delta=0, model_id=model_id, amount=earnings)
    # Branch 6: check UPGRADE_THRESHOLD here and call upgrade.maybe_upgrade(...)
```
Add repo helpers: `update_agent_stats`, `add_ledger_entry` (with `model_id`/`amount`), and `registry.reproject_agent` (rebuild the agent hash from the Postgres row, preserving the existing capability vector — read the stored vector bytes back with `r.hget(agent_key, VECTOR_FIELD)` so you don't re-embed every settle).

- [ ] **Update the seeder** to call `exchange.list_model` (replacing Branch 1 inline IPO).

### 3.3 Verification (Branch 3)

- [ ] AMM unit tests (offline, `WEAVE_DISABLED=1`), `tests/test_amm.py`:
```python
# constant product: buying raises price, k preserved across a trade (minus floors)
# selling lowers price; earnings raises price without changing shares
```
  Assert: after `buy(dc)`, `new_price > old_price` and `abs(S2*C2 - S*C) < 1e-6`; after `inject_earnings(+a)`, shares unchanged and price up; trades that round to ≤0 output raise `ValueError`.
- [ ] Ledger EMA test: `settle` with score 1.0 raises reputation toward 1, score 0.0 lowers it; check `new = 0.3*score + 0.7*old`.
- [ ] Live: run a task (as Branch 2) and watch the feed now also emit `reputation_changed`, `credits_changed`, `earnings_injected`, `price_changed`. `redis-cli ZSCORE model_prices gemini-3.5-flash` changes after a high-scoring task. `curl :8000/agents` shows derived price tracking the live model price (not the placeholder).

### 3.4 Dependency-ordered checklist (Branch 3)
1. `exchange.py` (list/buy/sell/inject/_commit_pool).
2. repo: `update_agent_stats`, `add_ledger_entry`, pool update reuse; `registry.reproject_agent`.
3. `ledger.py` settle.
4. `pricing.model_price` → live; broker calls `settle`.
5. seeder → `exchange.list_model`.
6. Tests (AMM + ledger), live loop, commit.

---

## Branch 4 — `feat/investing-users` (Phase 4: investing & users)

**Base:** `feat/ledger-exchange`  ·  **Purpose:** let users hold model shares and track P&L. Add `/models`, `/market`, `/trade`, `/portfolio/{id}`, `/users` (POST/GET). A user can buy a stock, prices move, the portfolio revalues.

### 4.1 Updates & cleanups

- [ ] **Confirm `repo`** has `adjust_user_credits`, `get_holding`, `upsert_holding`, `record_trade`, `list_holdings`, `list_users` (added in Branch 1). If any are stubs, implement now.
- [ ] **No schema change** — all tables exist from Branch 1.

### 4.2 New content

- [ ] **Portfolio service** — `backend/market/portfolio.py`:
```python
async def value(session, r, user_id) -> Portfolio:
    user = await repo.get_user(session, user_id)
    holdings = await repo.list_holdings(session, user_id)
    items, hv = [], 0.0
    for h in holdings:
        price = await registry.get_model_price(r, h.model_id) or 0.0
        val = float(h.shares) * price; hv += val
        items.append(Holding(model_id=h.model_id, shares=float(h.shares), price=price, value=val))
    return Portfolio(user_id=str(user_id), credits=float(user.credits),
                     holdings=items, holdings_value=hv, total=float(user.credits)+hv)
```

- [ ] **Trade orchestration** — `backend/market/trading.py` (ties user balance + holdings + the AMM; Weave-traced):
```python
import weave, uuid
from backend.market import exchange, registry, portfolio
from backend.ports.factory import get_event_bus
bus = get_event_bus()   # emit(r, X) below is shorthand for bus.publish(X); feed.emit lives only in LocalEventBus
from contracts.events import TradeExecuted, PortfolioChanged

@weave.op
async def trade(session, r, *, user_id, model_id, side, amount) -> dict:
    """BUY: amount = credits to spend. SELL: amount = shares to sell."""
    user = await repo.get_user(session, user_id)
    if side == "buy":
        if amount <= 0 or float(user.credits) < amount: raise ValueError("insufficient credits")
        shares_out, price = await exchange.buy(session, r, model_id=model_id, dc=amount)
        await repo.adjust_user_credits(session, user_id, -amount)
        await repo.upsert_holding_delta(session, user_id, model_id, +shares_out)
        spent, got = amount, shares_out
    elif side == "sell":
        h = await repo.get_holding(session, user_id, model_id)
        if h is None or amount <= 0 or float(h.shares) < amount: raise ValueError("insufficient shares")
        credits_out, price = await exchange.sell(session, r, model_id=model_id, ds=amount)
        await repo.adjust_user_credits(session, user_id, +credits_out)
        await repo.upsert_holding_delta(session, user_id, model_id, -amount)
        spent, got = amount, credits_out
    else:
        raise ValueError("side must be buy|sell")
    trade_id = uuid.uuid4().hex
    await repo.record_trade(session, user_id=user_id, model_id=model_id, side=side,
                            shares=(got if side=="buy" else amount),
                            credits=(spent if side=="buy" else got), price=price)
    await emit(r, TradeExecuted(trade_id=trade_id, user_id=str(user_id), model_id=model_id,
                                side=side, shares=(got if side=="buy" else amount),
                                credits=(spent if side=="buy" else got), price=price))
    p = await portfolio.value(session, r, user_id)
    await emit(r, PortfolioChanged(user_id=str(user_id), credits=p.credits,
                                   holdings_value=p.holdings_value, total=p.total))
    return {"trade_id": trade_id, "price": price,
            "shares": (got if side=="buy" else amount),
            "credits": (spent if side=="buy" else got)}
```
Add `repo.upsert_holding_delta(session, user_id, model_id, delta_shares)` (insert-or-add, clamp ≥0). The trade is one transaction: the AMM pool update, the user credit change, and the holding change all commit together (use the same `session`). Document the **atomicity invariant**: never debit credits without crediting shares.

- [ ] **API routes** (extend `backend/api`):
```python
@app.get("/models")           # board
async def get_models(session=Depends(get_session)):
    return [model_to_public(m, _price(m)) for m in await repo.list_models(session)]

@app.get("/market")           # snapshot + recent history
async def get_market(session=Depends(get_session)):
    r = get_redis()
    models = await get_models(session)
    hist = await read_price_history(r, count=500)   # XRANGE PRICE_HISTORY_KEY
    return {"models": models, "history": hist}

@app.post("/trade")           # {user_id, model_id, side, amount}
async def post_trade(body: dict, session=Depends(get_session)):
    r = get_redis()
    return await trading.trade(session, r, user_id=body["user_id"], model_id=body["model_id"],
                               side=body["side"], amount=float(body["amount"]))

@app.get("/portfolio/{user_id}")
async def get_portfolio(user_id: str, session=Depends(get_session)):
    return (await portfolio.value(session, get_redis(), user_id)).model_dump()

@app.post("/users")           # {name, email?, is_sim?} -> {user_id}
async def post_user(body: dict, session=Depends(get_session)):
    u = await repo.create_user(session, email=body.get("email"), name=body["name"],
                               credits=USER_START_CREDITS, is_sim=body.get("is_sim", False))
    return {"user_id": str(u.id)}

@app.get("/users")            # leaderboard by net worth
async def get_users(session=Depends(get_session)):
    r = get_redis(); out = []
    for u in await repo.list_users(session):
        p = await portfolio.value(session, r, u.id)
        out.append(UserPublic(user_id=str(u.id), name=u.name, email=u.email,
                              credits=p.credits, is_sim=u.is_sim, net_worth=p.total).model_dump())
    out.sort(key=lambda x: x["net_worth"], reverse=True)
    return out
```

### 4.3 Verification (Branch 4)

- [ ] Offline: `tests/test_trading.py` with a fake repo/exchange — buy debits credits and credits shares; sell reverses; buying then selling the received shares returns *less* credits than spent (AMM slippage), proving the curve.
- [ ] Live: seed, `POST /users {name:"alice"}` → `user_id`; `POST /trade {user_id, model_id:"gemini-3.5-flash", side:"buy", amount:100}` → returns shares + new price; `GET /portfolio/{user_id}` shows the position and a `total` ≈ start − slippage; a second buy moves the price up further; `GET /market` shows price history; `GET /users` ranks by net worth. Feed shows `trade_executed`, `price_changed`, `portfolio_changed`.

### 4.4 Dependency-ordered checklist (Branch 4)
1. repo `upsert_holding_delta`, confirm CRUD.
2. `portfolio.py`.
3. `trading.py`.
4. API routes `/models`,`/market`,`/trade`,`/portfolio`,`/users`.
5. Tests, live, commit.

---

## Branch 5 — `feat/simulation` (Phase 5: simulation layer)

**Base:** `feat/investing-users`  ·  **Purpose:** drive both markets with OpenAI agents (no static mockups). `/sim/start` and `/sim/stop` run task-posters and investors against the real API. Every sim decision is a `@weave.op`.

### 5.1 Updates & cleanups

- [ ] **Ensure sim users exist** — the seeder (Branch 1) already creates `is_sim=True` users. The sim picks them up via `GET /users` filtered to `is_sim`. If none exist, the sim auto-creates them via `POST /users`.
- [ ] **No schema change.**

### 5.2 New content

- [ ] **Sim runner** — `backend/sim/runner.py`. A controllable async loop with a module-level registry of tasks so `/sim/stop` can cancel:
```python
import asyncio, weave
_tasks: list[asyncio.Task] = []

@weave.op
def gen_goal() -> str:
    """OpenAI: produce one realistic, varied work goal (one line)."""
    from openai import OpenAI
    return OpenAI().responses.create(model=OPENAI_CHAT_MODEL,
        input="Invent ONE realistic short work request (writing/coding/research). One line.").output_text.strip()

@weave.op
def investor_decision(market_snapshot: dict, portfolio: dict) -> dict:
    """OpenAI: read the market + portfolio, decide {model_id, side, amount} or {action:'hold'}.
    Constrained JSON; caps trade size."""
    ...

async def _poster_loop(base_url, user_id, cadence_s):
    async with httpx.AsyncClient(base_url=base_url, timeout=120) as c:
        while True:
            await c.post("/task", json={"goal": gen_goal(), "user_id": user_id})
            await asyncio.sleep(cadence_s)

async def _investor_loop(base_url, user_id, cadence_s):
    async with httpx.AsyncClient(base_url=base_url, timeout=120) as c:
        while True:
            market = (await c.get("/market")).json()
            pf = (await c.get(f"/portfolio/{user_id}")).json()
            d = investor_decision(market, pf)
            if d.get("action") != "hold":
                amt = min(d["amount"], TRADE_CAP)   # cap trade size
                await c.post("/trade", json={"user_id": user_id, "model_id": d["model_id"],
                                             "side": d["side"], "amount": amt})
            await asyncio.sleep(cadence_s)

async def start(base_url, n_posters=2, n_investors=2, cadence_s=8.0): ...  # spawn loops, track in _tasks
async def stop(): ...  # cancel all _tasks
```
Add `TRADE_CAP`, `SIM_CADENCE_S`, `SIM_N_POSTERS`, `SIM_N_INVESTORS` to config. Constrain prompts so output is parseable JSON and bounded; on parse failure, default to `hold`.

- [ ] **API routes:**
```python
@app.post("/sim/start")
async def sim_start(body: dict | None = None):
    await sim_runner.start(BASE_URL, **(body or {})); return {"ok": True}

@app.post("/sim/stop")
async def sim_stop():
    await sim_runner.stop(); return {"ok": True}
```
`BASE_URL` defaults to `http://localhost:8000` (the API calls itself over HTTP, exactly as a real client would — build_doc §4.10 "calls the public API"). Keep the sim in-process for the demo; document that it could be a separate process later.

### 5.3 Verification (Branch 5)

- [ ] Offline: `tests/test_sim_decision.py` feeds a canned market snapshot to a monkeypatched `investor_decision` and asserts the runner caps trade size and falls back to `hold` on bad JSON.
- [ ] Live (needs OpenAI + GCP keys + agents running): `POST /seed`, `POST /sim/start {n_posters:2,n_investors:2}`, watch `/feed` fill with `task_posted`/`trade_executed`/`price_changed` with no human input; `POST /sim/stop` halts new events within one cadence; Weave shows `gen_goal` and `investor_decision` ops.

### 5.4 Dependency-ordered checklist (Branch 5)
1. config sim constants.
2. `sim/runner.py` (gen_goal, investor_decision, loops, start/stop).
3. API `/sim/start`,`/sim/stop`.
4. Tests, live, commit.

---

## Branch 6 — `feat/weave-upgrade` (Phase 6: upgrade logic + Weave curves)

**Base:** `feat/simulation`  ·  **Purpose:** agents reinvest credits to improve (raise margin / swap model stock / add tool), and Weave renders the curves that sell the demo.

### 6.1 Updates & cleanups

- [ ] **Hook the upgrade check into the ledger.** In `ledger.settle`, after the earnings injection, add:
```python
from backend.market.upgrade import maybe_upgrade
await maybe_upgrade(session, r, agent_id)
```
- [ ] **Keep agent creation+mutation in one function** (build_doc §4.7) so future gap-driven synthesis reuses it. Put `apply_agent_change(...)` in `upgrade.py` and have both upgrade paths call it.

### 6.2 New content

- [ ] **Upgrade logic** — `backend/market/upgrade.py` (Weave-traced):
```python
import weave
from backend.config import UPGRADE_THRESHOLD
from backend.db import repo
from backend.market import registry, exchange
from backend.ports.factory import get_event_bus, get_embeddings
bus = get_event_bus(); emb = get_embeddings()   # emit(r, X) == bus.publish(X); emb.embed_bytes for re-embedding
from contracts.events import AgentUpgraded

@weave.op
async def maybe_upgrade(session, r, agent_id) -> None:
    a = await repo.get_agent(session, agent_id)
    if a.credits < UPGRADE_THRESHOLD: return
    choice = _pick_upgrade(session, a)   # rule-based: margin | model_swap | add_tool
    cost = UPGRADE_THRESHOLD * 0.5
    detail = await apply_agent_change(session, r, agent_id, choice)
    await repo.adjust_agent_credits(session, agent_id, -cost)
    await registry.reproject_agent(r, session, agent_id)
    await emit(r, AgentUpgraded(agent_id=agent_id, change_type=choice["type"],
                                detail=detail, cost=cost))

async def apply_agent_change(session, r, agent_id, change) -> str:
    """Single mutation point. type in {price_bump, model_swap, add_tool}.
    - price_bump: margin += 0.1
    - model_swap: repoint agent.model to a stronger/cheaper-rising listed model
    - add_tool:  append a tool; update capability_text and RE-EMBED (re-project vector)
    Returns a human-readable detail string."""
    ...
```
`model_swap` chooses among **listed** models (query `registry.list_models_cached` / `repo.list_models`) by tier ladder `lite→flash→pro`; if capability changes (add_tool), re-embed `capability_text` and re-project the vector so KNN reflects the new capability. Add `repo.adjust_agent_credits`.

- [ ] **Weave custom views** — `backend/obs/weave_views.py` documents/creates the four panels (build_doc §4.11): rolling success rate (mean judge_score over a window), cost per task (sum of model-call costs / tasks — capture token/cost in `model_router.generate` as op attributes), per-model price history (from `price:history` / `PriceChanged` ops), investor portfolio returns (from `PortfolioChanged`). Implementation: attach metrics to ops via `weave` call attributes and define saved views; if programmatic view creation is awkward, document the exact Weave UI queries/filters to recreate them. Capture cost by recording `usage` from the GCP/OpenAI responses inside `generate` and returning it as part of the op's traced output.

- [ ] **Cost capture update** to `model_router.generate`: return/trace `{output, model, provider, usage}` (token counts) so Weave's cost-per-task view has data. Keep the agent `/run` contract returning just `{output}` (extract `.text`/`.output_text` for the agent, but trace usage in the op).

### 6.3 Verification (Branch 6)

- [ ] Offline: `tests/test_upgrade.py` — an agent above threshold triggers exactly one upgrade, credits drop by `cost`, and `model_swap` only targets listed models; `add_tool` re-embeds (assert the vector projection function is called).
- [ ] Live: run the sim long enough for a strong agent to cross `UPGRADE_THRESHOLD`; feed emits `agent_upgraded`; the agent's derived price/model changes on the next hire; Weave shows the four curves populated across the task stream (success rate rising, cost/task, price history, portfolio returns).

### 6.4 Dependency-ordered checklist (Branch 6)
1. `upgrade.py` (`maybe_upgrade`, `apply_agent_change`, `_pick_upgrade`); repo `adjust_agent_credits`.
2. ledger hook.
3. `model_router.generate` cost capture.
4. `obs/weave_views.py` + documented panels.
5. Tests, live, commit. Full demo dry-run (build_doc §7).

---

## Branch 7 — `feat/cloud-infra` (GCP adapters + deployment)

**Base:** `feat/weave-upgrade`  ·  **Purpose:** make the same code run on GCP by adding the **GCP adapters behind the existing ports** and provisioning the infra. No product-behaviour change — `RUNTIME_ENV=local` keeps working unchanged; `RUNTIME_ENV=gcp` runs the loop on Cloud Run + Cloud Tasks + Pub/Sub + Cloud SQL + Memorystore. The full design (topology, IAM, flows, gcloud) is `docs/cloud-architecture.md`; this branch implements it.

### 7.1 Updates & cleanups

- [ ] **Cloud SQL connectivity in `backend/infra/db.py`** — when `RUNTIME_ENV=gcp`, build the async engine through the **Cloud SQL Python Connector** (`cloud-sql-python-connector[asyncpg]` 1.20.3) with `create_async_connector(refresh_strategy="lazy")` and `ip_type=IPTypes.PRIVATE`, via SQLAlchemy's `async_creator`. Local path unchanged (plain `DATABASE_URL`). App code still only sees the engine/session — no call site changes.
- [ ] **Agent `/run` cloud behaviour** — `backend/agent/base.py`: if the request body carries a `result_url` (cloud dispatch), execute then POST `{subtask_id, agent_id, output, task_id}` to `result_url` with an OIDC token (audience = `API_URL`) and return `200` fast (Cloud Tasks acks on status, ignores body). If no `result_url` (local), return `{"output": ...}` as today. Single code path, gated on the field.
- [ ] **Confirm no Cloud SDK import leaks** — `rg -n "google.cloud|pubsub_v1|tasks_v2" backend | rg -v adapters` returns nothing (only `backend/adapters/gcp_*.py` may import Cloud SDKs).

### 7.2 New content

- [ ] **`backend/adapters/gcp_queue.py`** — `GcpTasksQueue.enqueue_run(dispatch)` creates a Cloud Task on queue `agent-{agent_id}` with `HttpRequest(POST {service_url}/run, body=..., oidc_token=OidcToken(service_account_email=TASKS_INVOKER_SA, audience=service_url))` and `name=dedup(subtask_id)` for enqueue-dedup. Uses `google-cloud-tasks` 2.22. (Code sketch: `docs/cloud-architecture.md` §4.)
- [ ] **`backend/adapters/gcp_event_bus.py`** — `GcpEventBus.publish(event)` does **both** Pub/Sub `publish` to `PUBSUB_TOPIC` **and** `XADD market:feed` (Memorystore replay) — dual-write (Open Q1). `subscribe(from_id)` runs a streaming pull on `PUBSUB_SUB` and yields decoded `MarketEvent`s; for `from_id="0"` it replays from the Redis Stream. In-process broadcaster fans one subscription to all SSE clients (demo: single instance; see `docs/cloud-architecture.md` §5). Uses `google-cloud-pubsub` 2.38.
- [ ] **`backend/adapters/gcp_embeddings.py`** — already created in Branch 1 (the only embeddings adapter); confirm it is selected and works against the deployed project.
- [ ] **Optional `backend/infra/secrets.py`** — read secrets via `google-cloud-secret-manager` 2.28 if not using `--set-secrets`. Prefer `--set-secrets` (no code) for the demo.
- [ ] **Deploy scripts** — `deploy/*.sh` + a `Makefile` (Open Q3: gcloud-scripts over Terraform for a solo dev). Steps mirror `docs/cloud-architecture.md` §10.2:
  - `deploy/00_infra.sh`: VPC connector, Cloud SQL (private IP), Memorystore (redis_7_2), secrets, Artifact Registry.
  - `deploy/10_build.sh`: `gcloud builds submit` the api + agent image(s).
  - `deploy/20_data.sh`: Cloud Run Jobs `migrate` (`alembic upgrade head`) + `seed`, `--execute-now --wait`.
  - `deploy/30_queues_topics.sh`: per-agent Cloud Tasks queues + Pub/Sub topic/subscription.
  - `deploy/40_services.sh`: deploy each `agent-<id>` (`--no-allow-unauthenticated`, `--min-instances=1`) and `api-broker` (`--allow-unauthenticated`, `--min/--max-instances=1`, `RUNTIME_ENV=gcp`, `API_URL`), then repoint each agent `service_url` to its Cloud Run URL (a seed/config update).
- [ ] **IAM** — per-service SAs (`sa-api-broker`, `sa-agent`, `sa-jobs`) with least-privilege roles per `docs/cloud-architecture.md` §7 (cloudtasks.enqueuer, run.invoker on agents, pubsub.publisher/subscriber, cloudsql.client, secretmanager.secretAccessor, aiplatform.user; `actAs` for OIDC minting).

### 7.3 Verification (Branch 7)

- [ ] **Local unmodified:** with `RUNTIME_ENV=local`, the full Branch 0–6 suite + live loop still pass (proves the seam didn't regress local).
- [ ] **Adapter unit tests** (no GCP calls): monkeypatch the Cloud SDK clients — assert `GcpTasksQueue.enqueue_run` builds a `Task` with the right queue path, OIDC audience, and dedup name; assert `GcpEventBus.publish` calls both Pub/Sub publish and the Redis `XADD`.
- [ ] **Cloud smoke (real GCP):** run `deploy/*.sh`; `POST https://api-broker.../seed`; `POST /task`; `curl -N /feed` shows the event sequence; a task moves reputation/credits and a model price; Weave shows traces from all services. `gcloud run jobs execute migrate/seed --wait` succeed.
- [ ] **Memorystore vector check:** after seed, the `agents_idx` FLAT index exists on Memorystore and KNN hiring returns candidates (proves native vector search works — `docs/cloud-architecture.md` §9). If `redis-py`'s `.ft()` helper hits an unsupported arg, fall back to `execute_command("FT.SEARCH", ...)`.

### 7.4 Dependency-ordered checklist (Branch 7)
1. `backend/infra/db.py` Cloud SQL connector path (gated on `RUNTIME_ENV`).
2. `agent/base.py` result-callback behaviour (gated on `result_url`).
3. `adapters/gcp_queue.py`, `adapters/gcp_event_bus.py` (+ optional `infra/secrets.py`).
4. `deploy/*.sh` + `Makefile`; IAM SAs + roles.
5. Adapter unit tests; local regression; cloud smoke; Memorystore vector check; commit.

---

## Cross-cutting: how the key mechanisms wire together

- **Derived pricing (where computed):** only in `backend/market/pricing.py` (`model_price` + `derived_price`). Consumed by the broker rank step and the `/agents` roster builder. Branch 2 returns a placeholder; Branch 3 reads `model_prices`/`model:{id}` from Redis. No stored agent price anywhere after Branch 1.
- **Model router (provider selection):** `backend/infra/model_router.generate(model, provider, ...)`. Provider comes from the `models.provider` column, projected to the `model:{id}` Redis hash, passed in the broker's `config` to the agent. The agent never hard-codes GCP vs OpenAI.
- **Earnings → exchange:** `ledger.settle` computes `earnings = EARN_RATE * (judge_score - 0.5) * hire_weight` and calls `exchange.inject_earnings`, which adds credits to the pool (no shares minted), reprojects Redis, and emits `earnings_injected` + `price_changed`. A bad score (<0.5) bleeds the stock.
- **AMM edge cases:** floors (`MIN_POOL_SHARES`, `MIN_POOL_CREDITS`), reject non-positive-output trades, clamp earnings (`±EARN_CLAMP`). All in `exchange.py`.
- **Seeder ordering:** list models (FK target) → upsert agents → project to Redis → create sim users. Every agent's `model` must be in `SEED_MODELS`.
- **Weave init once:** `backend/infra/weave_init.init_weave()` (idempotent flag), called from the API lifespan and each agent `main`; `WEAVE_DISABLED=1` for offline tests.
- **Atomic trade:** AMM pool update + user credit change + holding change commit in one `session` transaction.
- **Ports seam (one flag):** broker/ledger/exchange/api/sim use `get_queue()/get_event_bus()/get_embeddings()`; `RUNTIME_ENV` (`local`|`gcp`) selects adapters. No module imports a Cloud SDK directly. `feed.emit`/`feed.read_new` survive only inside `LocalEventBus`. Embeddings are GCP-only (fake in tests). See `docs/cloud-architecture.md` §3.
- **Dispatch is async:** `broker.run_task` only dispatches via `Queue`; output returns via the idempotent `broker.handle_run_result` (local in-proc, or cloud OIDC callback). Judge + `ledger.settle` live there so both paths behave identically.
- **Datastores:** local Postgres+Redis in Docker; cloud Cloud SQL + Memorystore (Branch 7) — app sees only `DATABASE_URL`/`REDIS_URL`. Memorystore 7.2+ supports the FLAT vector KNN natively (`docs/cloud-architecture.md` §9). Cloud Run deploy is **Branch 7 (`feat/cloud-infra`)**, in scope for this plan.

---

## Open decisions / risks to confirm

1. **`google-genai` response shapes.** Confirm `client.models.embed_content(...).embeddings[0].values` and `generate_content(...).text` against the installed `>=2.8` version (and that `EmbedContentConfig(output_dimensionality=768, task_type=...)` is honored). This is the single biggest correctness risk in the SDK migration. *Recommend: verify with a 5-line spike before Branch 1/2.*
2. **Real model IDs.** `gemini-3.5-flash` (stable), `gemini-3.1-pro-preview` (preview), `gemma-4-26b-a4b-it` are current; **`gemini-3.1-flash-lite-preview` in the seed roster is shut down (2026-05-25) → use stable `gemini-3.1-flash-lite`**. OpenAI's current default in SDK examples is the `gpt-5.5` family (seed uses `gpt-4.1`/`gpt-4.1-mini`). Confirm the exact ids on your GCP project / OpenAI account; the AMM/loop don't care about the strings but live calls 404 on wrong ids. (See `docs/cloud-architecture.md` §13 + Q5.)
3. **Background task execution for `/task`.** `run_task` dispatches via the `Queue` port; `LocalQueue` runs the HTTP call + `handle_run_result` in its own scope. Recommend in-process for the hackathon; flag if it proves flaky under the sim's load (fallback: await the local dispatch synchronously).
4. **`Decimal` vs `float` at the money boundary.** Plan computes the AMM in `float` and stores `Numeric`. Confirm acceptable precision for the demo (recommend yes; it's not real money), or switch the AMM to `Decimal` if you want exactness.
5. **Embeddings are GCP-only — credentials required locally.** The local-hash fallback is removed; seeding and hiring call GCP (`gemini-embedding-001` @ 768 dims, manual L2 norm). Local dev needs ADC/`GCP_PROJECT`; offline unit tests set `EMBEDDINGS_FAKE=1`. `VECTOR_DIM` must equal `output_dimensionality` (768) — change one, rebuild the index. Confirm 768 vs switching to `gemini-embedding-2` (auto-normalizes, multimodal) which would change DIM. (See `docs/cloud-architecture.md` §8 + Q4.)
6. **AMM tuning constants** (`EARN_RATE`, `W_PRICE`, `REP_ALPHA`, tier IPO prices). build_doc §9 says keep them fixed and conservative to avoid oscillation; the values in `config.py` are first guesses. Confirm or tune once after Branch 3 with a dry run.
7. **`users.name` length & agent name length drift** — plan standardizes to `String(255)` for agents (migration alters) and keeps `users.name` at 200. Confirm you're OK altering `agents.name` in `0002`.
8. **Sim trade semantics** — `amount` means *credits to spend* on buy and *shares to sell* on sell. Confirm this asymmetry is acceptable for `/trade` (it mirrors how an AMM buy/sell naturally parametrizes), or normalize both to credits.
9. **Cost capture for Weave** depends on the SDKs returning `usage`/token counts; confirm both providers expose it in the chosen call style (`responses.create` vs `chat.completions`).

---

## Self-review (against build_doc spec)

- Two coupled markets: agent loop (Branch 2/3) + model exchange (Branch 3) wired via `ledger.settle → exchange.inject_earnings` and `pricing.model_price` feeding broker rank. ✔
- Derived agent pricing (margin, not stored price): contracts + ORM + repo + registry + broker + roster (Branches 0/1/2/3). ✔
- Investing/portfolios with P&L and credit balances: Branch 4. ✔
- Simulation by OpenAI agents, no static mockups, mock_events.json retired: Branches 0 (retire) + 5 (build). ✔
- Models all on cloud; embeddings migrated to `google-genai`, **GCP-only (no local fallback; fake in tests)**: Branch 1. ✔
- Weave mandatory, `@weave.op` on every LLM + exchange op, custom views: every branch + Branch 6. ✔
- Ports/adapters seam (`Queue`/`EventBus`/`Embeddings`, `RUNTIME_ENV`): interfaces Branch 0, local adapters Branch 2, **GCP adapters + deploy Branch 7**. ✔
- Hire dispatch via `Queue` (in-proc local / Cloud Tasks cloud); event fan-out via `EventBus` (Redis Stream local / Pub/Sub cloud, Redis Stream replay): Branches 2 + 7. ✔
- Cloud datastores (Cloud SQL + Memorystore, VPC connector, Secret Manager) + Memorystore native vector KNN verified: Branch 7 / `docs/cloud-architecture.md`. ✔
- No frontend: excluded throughout. ✔
- Postgres tables/Redis keys/new events/new routes: Branches 0 (contracts) + 1 (schema) + 2/4/5 (routes). ✔
- Cleanups (smoke test rename, embeddings SDK→GCP-only, price→margin, CONTRACTS.md, requirements pinned, .env, dead import, User.name drift): Branches 0/1. ✔

## Execution Handoff

Plan complete and saved to `docs/plans/backend-plan.md`. Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks (REQUIRED SUB-SKILL: superpowers:subagent-driven-development).
2. **Inline Execution** — execute tasks in this session with checkpoints (REQUIRED SUB-SKILL: superpowers:executing-plans).

Start with Branch 0 and proceed in branch order.
