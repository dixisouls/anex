# Anex — Architecture

This document describes how Anex works end to end: the multi-agent orchestration loop,
the hybrid A2A execution model, the broker's hire pipeline, how Redis and Postgres divide
responsibility, the event-driven feed, the model exchange and its market microstructure,
the reputation ledger, and the ports/adapters seam that gives the whole system
local↔cloud parity.

> **Theme: multi-agent orchestration as a market.** Instead of a fixed agent graph, Anex
> treats "who should do this work" as a hiring decision made at runtime, priced against a
> live budget, and graded after the fact. The grade feeds back into reputation and into
> the price of the model that did the work.

---

## Table of contents

1. [System overview](#system-overview)
2. [The orchestration loop](#the-orchestration-loop)
3. [Hybrid A2A](#hybrid-a2a)
4. [The broker pipeline: decompose → recall → re-rank → dispatch → judge → settle](#the-broker-pipeline)
5. [Agents and the capability catalog](#agents-and-the-capability-catalog)
6. [Redis: the hot path](#redis)
7. [Postgres: the system of record](#postgres)
8. [The event bus and the SSE feed](#the-event-bus-and-the-sse-feed)
9. [The model exchange (AMM)](#the-model-exchange)
10. [Market microstructure: fundamentals, quotes, and the arb kernel](#market-microstructure)
11. [The ledger: reputation, credits, earnings](#the-ledger)
12. [The model router (multi-provider LLM access)](#the-model-router)
13. [Ports & adapters: local↔cloud parity](#ports--adapters)
14. [Concurrency and backpressure](#concurrency-and-backpressure)
15. [Observability](#observability)

---

## System overview

```
                         ┌──────────────────────────────────────────────┐
                         │                 FastAPI app                    │
   human / sim poster ──▶│  POST /task   GET /feed (SSE)   POST /trade    │◀── human / sim investor
                         │  /agents /models /market /portfolio /auth ...  │
                         └───┬───────────────┬───────────────┬───────────┘
                             │               │               │
                  ┌──────────▼─────┐   ┌─────▼──────┐   ┌────▼─────────┐
                  │   BROKER       │   │  EXCHANGE  │   │   LEDGER     │
                  │ decompose      │   │  AMM buy/  │   │ reputation   │
                  │ recall+rerank  │   │  sell/arb  │   │ credits      │
                  │ dispatch(A2A)  │   │  quotes    │   │ earnings     │
                  └───┬────────┬───┘   └─────┬──────┘   └────┬─────────┘
                      │        │             │               │
            A2A POST  │        │ judge       │               │
        /tasks/send   ▼        ▼             ▼               ▼
              ┌───────────────┐        ┌──────────────────────────────────┐
              │ GENERIC       │        │  Redis (hot path)   Postgres (truth)│
              │ WORKER POOL   │        │  vector index       users/agents    │
              │ (A2A agents)  │        │  market:feed stream models/tasks    │
              └───────┬───────┘        │  prices/leaderboard subtasks/trades │
                      │                │  price history      ledger_entries  │
                      ▼                └──────────────────────────────────┘
        ┌──────────────────────────┐
        │  Model router            │  → GCP Gemini / Vertex OpenAI-compat / OpenAI
        └──────────────────────────┘
```

Two markets share one substrate:

- **The labor market** — agents are hired to do subtasks. Hiring is driven by embedding
  recall + LLM re-rank, paid in credits, and graded by an LLM judge.
- **The asset market** — each underlying model is a tradable stock on an AMM. Judge
  scores move a model's fundamental value; investors trade the price around it.

The bridge between them is the **ledger**: when an agent's work is judged, its earnings
are injected into its model's stock pool, repricing the asset.

---

## The orchestration loop

A single posted goal flows through the system like this:

1. **Post** — `POST /task` validates the poster's budget against live credits, persists a
   `Task` row, and kicks off the broker pipeline asynchronously (under a global
   concurrency semaphore).
2. **Decompose** — the broker asks an LLM to split the goal into 1–4 ordered,
   self-contained subtasks, worded to match the roster's advertised skills.
3. **Per subtask, in order:**
   - **Recall** candidate agents from the Redis vector index (KNN over capability
     embeddings).
   - **Resolve tiers** — collapse vector hits to one affordable tier variant per
     capability family, capped at the poster's `preferred_tier` and remaining budget.
   - **Re-rank** the finalists with an LLM to pick the single best-fit agent.
   - **Charge the hire** (debit poster, credit the agent's treasury) in its own committed
     transaction.
   - **Dispatch** the work over A2A to a worker, passing prior subtask results as context.
   - **Judge** the returned output (LLM, 0.0–1.0 rubric).
   - **Settle** — update reputation (EMA), award credits, and inject earnings into the
     model's stock.
4. **Stream** — every transition publishes a typed event to the `market:feed` Redis
   stream, which the SSE `/feed` endpoint replays to the UI in real time.
5. **Complete** — the task is marked complete; the persisted subtask pipeline (candidates,
   hire price, output preview, judge score) is queryable via task history.

Each subtask runs sequentially because later steps consume earlier outputs
(`PRIOR RESULTS` are fed into the agent prompt), but multiple *tasks* run concurrently up
to `MAX_CONCURRENT_TASKS`.

---

## Hybrid A2A

Anex implements the **Google Agent-to-Agent (A2A) protocol** for delegation, but applies
it in a hybrid way that is one of the project's core design choices.

### The A2A contract

Defined in [`contracts/a2a.py`](contracts/a2a.py). Each agent worker is A2A-compliant:

| Endpoint | Purpose |
|----------|---------|
| `GET /.well-known/agent.json` | Serves an **AgentCard** — name, description, capabilities, and skills |
| `POST /tasks/send` | Accepts an **A2ATask** (a `Message` of `TextPart`s + metadata) and returns an **A2ATaskResult** with an `Artifact` |
| `GET /healthz` | Liveness |

The types mirror the spec: `AgentCard`, `AgentSkill`, `A2ATask`, `Message`, `TextPart`,
`Artifact`, `TaskStatus`, and the `TaskState` state machine
(`submitted → working → completed | failed | …`).

### Why "hybrid"

A naïve implementation would run **one service per agent** — 119 of them. Anex instead
separates **logical agents** from **physical execution**:

- **Logical agents** are the 119 entries in the registry: each is a *capability × service
  tier* identity (e.g. `coder-pro`, `coder-flash`, `coder-lite`), with its own model,
  reputation, credits, price, and capability embedding.
- **Physical execution** is a small **shared, generic worker pool**. Every logical
  agent's `service_url` round-robins onto a worker. A worker is *self-describing* — it can
  resolve its own model/prompt from seed data — but in practice the **broker passes the
  full model config in the A2A task metadata per dispatch** (`metadata.config` =
  `{model, provider, system, tools}`). So any worker can embody any agent for any single
  call.

This is the hybrid: the **A2A protocol and agent identities are real and intact**
(distinct AgentCards, distinct hiring, distinct reputations), while the **execution
substrate is pooled and stateless**. The benefits:

- 119 specialists, but only a handful of processes to run and scale.
- Workers are horizontally scalable and interchangeable — add capacity without touching
  the roster.
- The same `Queue` port that does an in-process HTTP A2A call locally maps cleanly to
  **Cloud Tasks HTTP-push with OIDC** in cloud (one queue per agent), with no change to
  the broker.

The dispatch path: `broker → Queue.enqueue_run_and_wait(RunDispatch) → LocalQueue` posts
an A2A `tasks/send` to the worker's `service_url`, extracts the artifact text, and routes
the result back into `broker.handle_run_result` for judging and settlement.

---

## The broker pipeline

[`backend/market/broker.py`](backend/market/broker.py) is the orchestrator. The stages:

### 1. Decompose
`decompose()` prompts an LLM with the goal plus a **deduplicated, evenly-sampled catalog
of the roster's real skills**, asking for 1–4 ordered, self-contained subtask strings.
Wording subtasks against advertised skills is deliberate: it makes the downstream
embedding recall land on agents that actually exist. Falls back to `[goal]` on any parse
failure.

### 2. Recall (vector KNN)
`rank()` embeds the subtask text as a `RETRIEVAL_QUERY` and runs a KNN search over the
Redis vector index (`registry.search`). Recall is broad (`RANK_RECALL_K`, default 10) to
favor coverage over precision — precision is the re-rank's job.

### 3. Tier resolution + budget gating
`resolve_tier_variants()` dedupes the hits to one capability family each and, for each,
selects the **highest allowed tier** (up to the poster's `preferred_tier`) whose
**derived hire price** fits the remaining budget. Hire price is
`model_price × (1 + margin)`, read live from the model's AMM pool. Subtasks with no
affordable candidate are **skipped** with a reason that surfaces in the UI.

### 4. Re-rank (LLM)
`select_best()` takes the top finalists (`RERANK_FINALISTS`, default 6) and asks a cheap
LLM call to pick the single best agent by inspecting each finalist's name, skills, and
capability text. Cosine recall is good at breadth but often returns an over-narrow nearest
neighbor; the re-rank fixes the "close but wrong" mismatch. Falls back to the cosine top
on any error.

The cosine candidates also carry a transparent linear score for ranking and display:
`final = W_MATCH·match + W_REP·reputation − W_PRICE·price`.

### 5. Dispatch (A2A)
The hire is charged, then `queue.enqueue_run_and_wait()` sends the A2A task to a worker
with the resolved config and a prompt that includes the original goal and prior subtask
outputs.

### 6. Judge + settle
On a returned output, `handle_run_result()`:
- guards idempotency (`subtask_already_scored` via Redis `SETNX`),
- publishes `task_executed`,
- calls `judge()` (LLM, anchored 0.0–1.0 rubric),
- publishes `task_scored`,
- persists the result, and
- calls `ledger.settle()` to update reputation/credits and inject earnings into the model
  stock.

---

## Agents and the capability catalog

The roster is **data-driven**. [`backend/market/data/capabilities.json`](backend/market/data/capabilities.json)
defines **41 capability families** (writer, coder, debugger, researcher, analyst, SQL
analyst, security, devops, …). Each family declares its skills, a capability blurb, a
margin, a suggested system prompt, and the model bound to each service tier.

[`capabilities.py`](backend/market/capabilities.py) expands these into **119 tiered
agents** (`pro` / `flash` / `lite` variants), where tier rank is `pro=3, flash=2,
lite=1`. Pricing is tier-driven through the bound model's stock price, so a `pro` agent on
a Gemini Pro model costs more to hire than its `lite` sibling.

For the vector index, only one **primary tier per capability** is embedded (the highest
tier offered), so recall returns one row per family; tier selection then happens against
the budget. The document embedded is
`"{name}. Skills: {skills}. {capability_text}"` — name and skills are included on purpose
so retrieval aligns with how subtasks are phrased.

---

## Redis

Redis 8 is the **hot path**. Postgres is the durable source of truth; Redis holds
**projections that are fully rebuildable from Postgres**, so every read-heavy request hits
Redis. Redis 8 ships the query engine and vector search **in core** — no redis-stack image
or third-party module needed. Key conventions live in [`backend/config.py`](backend/config.py).

| Structure | Key(s) | Purpose |
|-----------|--------|---------|
| **Vector index** | `agents_idx` over `agent:*` HASHes, field `embedding` | FLAT KNN (COSINE, 768-dim) hiring recall via `FT.CREATE` / `FT.SEARCH` (dialect 2) |
| **Agent hashes** | `agent:{id}` | Projected agent record + raw float32 capability vector |
| **Model hashes** | `model:{id}` | Live price, bid/ask, spread, depth, fundamental, session OHLC, volume |
| **Price book** | `model_prices` (ZSET) | Models sorted by current price |
| **Event stream** | `market:feed` (STREAM) | Every market event; replayed to SSE `/feed` |
| **Price history** | `price:history:{model}` (STREAM, capped) | Per-model ticks rolled into OHLCV bars |
| **Leaderboard** | `leaderboard` (ZSET) | Agents by reputation |
| **Idempotency** | `scored:{subtask}` (`SETNX`) | Score each subtask exactly once |
| **Hire prices** | `hire:{subtask}` (TTL) | Remember the hire price for award capping at settle time |
| **Session** | `market:session` | Per-model session-open prices |

Two important details:

- **`decode_responses=False`** — the client returns raw bytes because the capability
  vector is stored as raw `float32` bytes on the agent hash; a decoding client would try
  to UTF-8 decode and corrupt it. Text fields are decoded explicitly via `util.to_str`.
- **RESP2 protocol** — pinned because `redis-py`'s `FT.SEARCH` does not parse Redis 8's
  RESP3 dict replies.

Transient Redis timeouts are retried with exponential backoff (`with_redis_retry`).

---

## Postgres

[`backend/db/models.py`](backend/db/models.py) defines the source of truth (SQLAlchemy
async + asyncpg, migrated with Alembic):

| Table | Holds |
|-------|-------|
| `users` | Humans and sim users; credits, auth hash, `is_sim` |
| `models` | Tradable model stocks; AMM pool (`pool_shares`, `pool_credits`), IPO price |
| `agents` | The roster; capability, tier, model, reputation, credits, hires/wins, `service_url` |
| `tasks` | Posted goals + status; soft-hide per user |
| `subtasks` | Full pipeline state: text, assigned agent, candidates JSON, hire price, budget remaining, output preview, judge score, skip reason |
| `holdings` | Per-user share positions |
| `trades` | Executed trades (side, shares, credits, price) |
| `ledger_entries` | Hire / award / earnings audit trail with reputation before/after |

The subtask table persisting **candidates, hire price, and judge score** is what makes
task history reconstructable after the fact — the UI's pipeline view is rendered from it,
not from ephemeral events. A subtask's display **stage** (`posted → ranked → hired →
executed → scored`) is derived from which columns are populated.

---

## The event bus and the SSE feed

Anex is event-driven. Every meaningful state change publishes a **typed Pydantic event**
(discriminated union in [`contracts/events.py`](contracts/events.py)):
`task_posted`, `candidates_ranked`, `agent_hired`, `subtask_skipped`, `task_executed`,
`task_scored`, `reputation_changed`, `credits_changed`, `model_listed`, `price_changed`,
`earnings_injected`, `trade_executed`, `portfolio_changed`.

Publication goes through the **`EventBus` port**. Locally, `LocalEventBus` writes to the
`market:feed` Redis stream (`XADD`) and reads via blocking `XREAD`. The `GET /feed`
endpoint (`sse-starlette`) first replays a backlog of recent events, then tails the stream
live — so a client that connects mid-session immediately sees consistent state and then
streams updates.

In cloud the same port maps to **Pub/Sub** for fan-out, with the Redis stream retained as
a replay log — application code never changes.

---

## The model exchange

[`backend/market/exchange.py`](backend/market/exchange.py) implements a
**constant-product automated market maker** (`x · y = k`), where for each model the pool
holds `shares` and `credits` and the mid price is `credits / shares`.

- **List (IPO)** — a model is listed with `IPO_SHARES` shares and `tier_ipo_price ×
  shares` credits, setting its opening price by tier (`pro=50, flash=20, lite=8`).
- **Buy** — spend `dc` credits; `shares_out = s − k/(c+dc)`. Price rises.
- **Sell** — return `ds` shares; `credits_out = c − k/(s+ds)`. Price falls.
- **Inject earnings** — add credits to the pool **without issuing shares**. This is the
  fundamentals channel: it lifts price when an agent does good work (and the converse for
  poor work), driven by judge scores via the ledger.
- **Arb** — a mean-reverting nudge toward fundamental value (see below).

Trades are orchestrated in [`trading.py`](backend/market/trading.py), which moves the AMM
pool, the user's credits, and their holdings atomically in one DB session, records the
trade, and emits `trade_executed` + `portfolio_changed`. A pool floor prevents draining a
side to zero.

---

## Market microstructure

[`backend/market/dynamics.py`](backend/market/dynamics.py) is what makes the exchange feel
like a real market rather than a bonding curve. It maintains **two prices**:

- **`P` — the tradable mid**: `credits/shares` on the AMM, what buys and sells move.
- **`F` — the fundamental fair value**: a separate per-model value moved by judge scores.
  Good work (`score > EARN_BASELINE`) raises `F`; poor work lowers it, as a log-return
  scaled by pool size.

A background **arbitrage kernel** ([`arb_runner.py`](backend/market/arb_runner.py)) ticks
every `ARB_INTERVAL_S` across all models and applies an **Ornstein–Uhlenbeck**
adjustment that pulls `P` toward `F` plus exogenous noise:

```
d_log = κ_tier · (F − P)/P · dt  +  σ_tier · √dt · N(0,1)     (clamped to ±ARB_MAX_BPS)
```

Mean-reversion speed `κ` and volatility `σ` are **tier-scaled** — `lite` models are
jumpier than `pro`. Bid/ask **quotes** are derived from the average slippage of a small
`QUOTE_SIZE` trade on each side, giving a realistic spread; **depth** is `√(shares·credits)`.
There's also a GBM path generator used to seed plausible historical charts.

The net effect: prices wander and trend on real order flow, but are anchored to a
quality-driven fundamental — so the market gradually prices up the models that consistently
do good work.

---

## The ledger

[`backend/market/ledger.py`](backend/market/ledger.py) is the bridge between the labor
market and the asset market. Two operations:

- **`charge_hire`** — debits the poster and credits the hired agent's treasury (credits are
  conserved), in its **own committed transaction** so a later settle reads the updated
  balance. Emits `credits_changed` + `portfolio_changed`.
- **`settle`** (post-judge) —
  - **Reputation** updates as an exponential moving average:
    `rep' = α·score + (1−α)·rep` (`REP_ALPHA = 0.3`).
  - **Credit award** proportional to score and price, capped at a fraction of the hire
    price.
  - **Earnings → fundamentals**: the judge score is converted to raw earnings
    (`EARN_RATE·(score − EARN_BASELINE)`), which both updates the model's fundamental value
    `F` and passes a fraction (`POOL_PASS_THROUGH`) into the AMM pool via
    `exchange.inject_earnings`.
  - Updates the leaderboard, re-projects the agent to Redis, and writes
    `award` + `earnings` ledger entries.

This closes the loop: **work quality → reputation + the price of the model that did it.**

---

## The model router

[`backend/infra/model_router.py`](backend/infra/model_router.py) is the single entry point
for all chat generation, mapping `(model, provider)` to a client:

| Provider | Path |
|----------|------|
| `gcp` | Native Gemini via `google-genai` (Vertex AI) — broker, judge, and most workers |
| `vertex_openai` | Third-party models on Vertex AI's OpenAI-compat endpoint (LLaMA 4, Grok, GLM) using a gcloud access token |
| `openai` | Standard OpenAI `chat.completions` / Responses API — worker variety + the whole simulation |

It returns a uniform `{output, usage, model, provider}` so **Weave** traces token counts
across every provider. Embeddings have their own entry point
([`infra/embeddings.py`](backend/infra/embeddings.py)) — GCP `gemini-embedding-001` at 768
dims, L2-normalized; a `FakeEmbeddings` adapter is used only in offline tests.

---

## Ports & adapters

The product loop is environment-agnostic. Only three concerns differ between a laptop and
GCP, and each sits behind a **port** interface resolved by a single factory
([`backend/ports/factory.py`](backend/ports/factory.py)) driven by `RUNTIME_ENV`:

| Port | Local adapter | Cloud adapter | Concern |
|------|---------------|---------------|---------|
| **`Queue`** | in-process HTTP A2A (`httpx`) | Cloud Tasks (HTTP-push + OIDC), one queue per agent | Dispatch a hire |
| **`EventBus`** | Redis Stream `XADD`/`XREAD` | Pub/Sub topic + subscription (Redis stream kept as replay log) | Fan out market events to `/feed` |
| **`Embeddings`** | GCP `google-genai` | GCP `google-genai` (same) | Text → vector |

Application code (broker, ledger, exchange, API, sim) imports only the port interfaces —
never a Cloud SDK directly — so the same code runs locally and on GCP by flipping one env
var. Durable truth (Postgres) and the hot path (Redis) are just connection-string swaps
(Cloud SQL / Memorystore in cloud).

---

## Concurrency and backpressure

- **Task pool** — `POST /task` runs the broker pipeline under a global
  `asyncio.Semaphore` sized by `MAX_CONCURRENT_TASKS`, so a flood of posts can't overwhelm
  the LLM providers. `GET /task/slots` exposes free capacity, which sim posters poll for
  **backpressure** before posting.
- **Worker concurrency** — each A2A worker runs its blocking LLM call in a threadpool
  (`run_in_threadpool`), so one worker process can serve concurrent dispatches without
  head-of-line blocking.
- **Sync LLM calls off the loop** — decompose, judge, sim goal generation, and LLM
  investor decisions run via `asyncio.to_thread` / threadpools so they don't block the
  event loop.
- **Transient retries** — Redis timeouts and sim HTTP errors retry with exponential
  backoff.
- **Transactional discipline** — hires commit before dispatch (so the worker's separate
  DB session can see the subtask rows); scoring is idempotent via a Redis `SETNX` guard.

---

## Observability

Every LLM and exchange operation is decorated with `@weave.op`, so **Weave** captures a
full trace tree per task: `run_task → decompose → rank → select_best → judge → settle`,
plus token usage from the model router and every AMM operation. The judge, broker, worker
`execute`, sim goal generation, and LLM investor decisions are all traced. Set
`WEAVE_PROJECT`; disable with `WEAVE_DISABLED=1` (tests set this automatically).
