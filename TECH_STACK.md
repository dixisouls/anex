# Anex — Technologies & Full Tech Stack

Every technology used in Anex and the reason it's there. Versions reflect what the project
was built and verified against.

---

## At a glance

| Layer | Technology |
|-------|------------|
| **Orchestration / agent protocol** | Google **A2A** (Agent-to-Agent) spec — AgentCards, `tasks/send`, Artifacts |
| **API & services** | **FastAPI**, **Uvicorn**, **Pydantic v2**, **httpx**, **SSE-Starlette** |
| **Hot path / vectors / events** | **Redis 8** (native vector search, streams, sorted sets) |
| **System of record** | **Postgres 16** via **SQLAlchemy 2 (async)** + **asyncpg**, migrated with **Alembic** |
| **Models — chat** | **GCP Gemini Enterprise Agent Platform** (`google-genai`), **OpenAI**, **Vertex AI OpenAI-compat** (LLaMA / Grok / GLM) |
| **Models — embeddings** | GCP **`gemini-embedding-001`** (768-dim, normalized) |
| **Simulation** | OpenAI (Responses API, structured JSON) + pure-Python quant strategies + NumPy |
| **Observability** | **Weave** (W&B) tracing on every LLM + exchange op |
| **Frontend** | **Next.js 16** (App Router), **React 19**, **Tailwind CSS 4**, **lightweight-charts** |
| **Packaging / deploy** | **Docker** + **docker-compose**; cloud target: **GCP Cloud Run / Cloud Tasks / Pub/Sub / Cloud SQL / Memorystore** |

---

## Backend — core / hot path

| Technology | Version | Why it's used |
|------------|---------|---------------|
| **Python** | 3.12 | Backend language. |
| **Redis** | 8.0 | The hot path. Redis 8 ships the **query engine and vector KNN in core** (no redis-stack, no third-party module), so the agent **hiring index** (FLAT KNN over a HASH), the **`market:feed` event stream**, **per-model price-history streams**, the **reputation leaderboard** (ZSET), the **price book** (ZSET), and **idempotency locks** (`SETNX`) all live in one engine. Memorystore-compatible for cloud. |
| **Pydantic** | 2.13+ | All contracts: A2A types, the discriminated-union market events, and core data objects. Strict validation at every boundary. |
| **NumPy** | 2.4 | Embedding vectors (float32, L2-normalized) and simulation math. |

### Why Redis is more than a cache
Postgres is the durable truth; Redis holds **rebuildable projections** that every
read-heavy request hits. Two non-obvious choices: the client runs with
`decode_responses=False` (the capability vector is stored as raw `float32` bytes on the
agent hash, so a decoding client would corrupt it), and **RESP2** is pinned because
`redis-py`'s `FT.SEARCH` doesn't parse Redis 8's RESP3 dict replies. See
[ARCHITECTURE.md](ARCHITECTURE.md#redis).

---

## Backend — persistence

| Technology | Version | Why it's used |
|------------|---------|---------------|
| **PostgreSQL** | 16 | System of record: users, model stocks (AMM pools), agents, tasks, subtasks (full pipeline state), holdings, trades, ledger entries. |
| **SQLAlchemy** | 2.0 (asyncio) | Async ORM. ORM models are deliberately separate from the Pydantic contract shapes. |
| **asyncpg** | 0.31+ | Async Postgres driver. |
| **Alembic** | 1.18+ | Schema migrations. |

---

## Backend — API, broker transport, streaming

| Technology | Version | Why it's used |
|------------|---------|---------------|
| **FastAPI** | 0.136+ | The API surface: task posting, trading, portfolios, auth, agents/models/market reads, the SSE feed, and internal run-result callbacks. |
| **Uvicorn** | 0.49+ | ASGI server for the API and every A2A worker. |
| **httpx** | 0.28+ | Broker → agent **A2A** dispatch (the local `Queue` adapter) and the simulation's HTTP calls against the public API. |
| **SSE-Starlette** | 3.4+ | `EventSourceResponse` powering `GET /feed` — backlog replay then live tail of the Redis stream. |

---

## Models & providers

Anex is deliberately **multi-provider**. A single model router
([`backend/infra/model_router.py`](backend/infra/model_router.py)) maps
`(model, provider)` to the right client and returns a uniform result so token usage is
traced everywhere.

| Provider | SDK | Role |
|----------|-----|------|
| **GCP Gemini Enterprise Agent Platform** | `google-genai` 2.8+ | Primary chat for the **broker** (decompose + re-rank), the **judge**, and most **workers**; also **embeddings** (`gemini-embedding-001`). |
| **Vertex AI OpenAI-compat endpoint** | `openai` (pointed at Vertex) | Third-party tradable models — **LLaMA 4 Maverick, Grok 4.1, GLM** — accessed via a gcloud access token. These exist as **stocks** on the exchange and as worker model options. |
| **OpenAI** | `openai` 2.41+ | Worker variety, plus the **entire simulation**: poster goal generation and LLM investor decisions (Responses API with strict JSON schema). |

**Tradable model roster** spans Gemini (Pro / Flash / Flash-Lite), Gemma, and the Vertex
third-party models — each listed on the AMM with a tier-based IPO price.

### Cloud adapters (installed everywhere; only active when `RUNTIME_ENV=gcp`)
`google-cloud-tasks` (hire dispatch via HTTP-push + OIDC), `google-cloud-pubsub` (event
fan-out to SSE), `google-cloud-secret-manager` (secrets at startup), and
`cloud-sql-python-connector` (Cloud SQL private-IP connectivity). They're imported lazily,
so local dev never needs them at import time.

---

## Simulation stack

| Technology | Role |
|------------|------|
| **OpenAI Responses API** | LLM investor cohorts (retail, whales) make decisions as **structured JSON** with a strict schema; posters invent realistic goals. |
| **Pure-Python strategies + NumPy/`math`** | Math investor cohorts (market-makers, quants) compute momentum / value / stat-arb / market-making signals with softmax position selection — fast, no network. |
| **httpx + asyncio** | Each sim user is an async loop hitting the same public API a human would, with jittered cadence and slot-based backpressure. |

Full design in [SIMULATION.md](SIMULATION.md).

---

## Observability

| Technology | Version | Why it's used |
|------------|---------|---------------|
| **Weave** (Weights & Biases) | 0.52+ | Every LLM and exchange operation is a `@weave.op`, producing a full trace tree per task (`run_task → decompose → rank → select_best → judge → settle`) with cross-provider token usage. Mandatory in the build; disabled in tests. |

---

## Frontend

| Technology | Version | Why it's used |
|------------|---------|---------------|
| **Next.js** | 16 (App Router) | The live trading-floor dashboard. |
| **React** | 19 | UI. |
| **Tailwind CSS** | 4 | Styling. |
| **lightweight-charts** | 5 | Candlestick / price charts for the model exchange. |
| **react-markdown + remark-gfm** | — | Rendering agent outputs and task threads. |
| **motion** | 12 | Animations on the trading floor / pipeline. |

The frontend consumes the backend over **SSE** (live feed) and **REST**, with two main
routes: `/exchange` (watchlist, charts, order ticket, portfolio) and `/network` (post
tasks, agent roster, live broker/subtask pipeline). See
[frontend/README.md](frontend/README.md).

---

## Packaging & deployment

| Technology | Role |
|------------|------|
| **Docker** | Single backend image reused for migrations, seeding, the API, and the worker pool. |
| **docker-compose** | Local datastores (Postgres 16 + Redis 8) and optional API/seed/migrate services under profiles. |
| **GCP (cloud target)** | Cloud Run (API+broker; one parameterized image for the worker pool), Cloud Run Jobs (migrate, seed), Cloud Tasks (per-agent hire queues), Pub/Sub (event fan-out), Cloud SQL (Postgres), Memorystore (Redis), Secret Manager, Artifact Registry. The **ports/adapters seam** means the same code targets both local and cloud by flipping `RUNTIME_ENV`. |

---

## Design principles baked into the stack

- **Two datastores, clear roles** — Postgres is truth; Redis is the rebuildable hot path.
- **Multi-provider by design** — one router, three providers, uniform tracing.
- **Protocol-real, execution-pooled** — genuine Google A2A agents on a shared generic
  worker pool ([hybrid A2A](ARCHITECTURE.md#hybrid-a2a)).
- **Local↔cloud parity** — three ports (`Queue`, `EventBus`, `Embeddings`) isolate every
  environment difference behind one env var.
- **Event-driven** — typed events on a stream drive the entire live UI.
- **Everything traced** — Weave on every model and market operation.
