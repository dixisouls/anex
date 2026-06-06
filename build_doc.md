# Agent Bazaar: Build Documentation

A self-organizing agent marketplace fused with a live model exchange. Worker agents advertise capabilities and a broker hires the best one for each incoming subtask. Every agent runs on an underlying model, and **each model is a tradable stock**: its price rises and falls on a live exchange driven by how well agents using it perform and by investors buying and selling shares. The two markets are one loop. Good agents win tasks, which lifts the "earnings" of the model they run on, which lifts that model's stock, which raises what those agents cost to hire, which pushes the broker to rotate, which moves investor money. Market selection, agent upgrades, and a live model economy all feed each other.

Built for WeaveHacks 4 (Multi-Agent Orchestration). Three headline mechanisms: market selection (the broker hiring the best agent), agent upgrades (agents reinvesting to improve), and the model exchange (a NASDAQ-for-models where prices are live and investable). Weave traces every model call and renders the improvement and market curves. Gap-driven agent synthesis is designed for but not built in the first pass.

This is a solo build. The original three-track parallel plan is replaced by a sequential phase order in Section 8. The core broker and worker loop is unchanged; everything new layers on top of it.

---

## 1. System Overview

### The two coupled markets

**Agent Marketplace** (the existing loop): a user posts a goal, the broker decomposes it, hires the best agent per subtask, the agent executes, a judge scores it, and the ledger updates reputation and credits.

**Model Exchange** (new): every model an agent can run on (Gemini and others on the GCP Gemini Enterprise Agent Platform, plus OpenAI models) is listed as a stock with a live price. Prices move from two forces: **earnings** (agents performing well on a model inject value into that model's stock) and **trading** (investors buying and selling shares). Agents do not set a flat price anymore: an agent's hire cost is **derived** from its model's current stock price plus the agent's own margin.

### The unified loop

1. A user (real, or a simulated OpenAI agent in the demo) posts a goal.
2. The broker decomposes the goal into subtasks.
3. For each subtask, the broker searches the registry for agents whose advertised capability matches, ranks candidates by semantic fit plus reputation minus **derived price** (which tracks the model's live stock), and hires one.
4. The hired agent executes the subtask on its underlying model.
5. The judge scores the output against the subtask.
6. The ledger updates the agent's reputation and credit balance, and **injects earnings into the agent's model stock** in proportion to the score. Good performance lifts the model's price.
7. Investors (real, or simulated OpenAI agents) watch the feed and **buy or sell shares** of models on the exchange. Trades move prices along an automated market maker curve.
8. Because agent price is derived from model price, a rising model makes its agents pricier, nudging the broker toward cheaper rising models, which moves investor money again.
9. When an agent's credits cross a threshold it reinvests in an upgrade (raise its margin, swap to a stronger model stock, or add a tool).
10. Across a stream of tasks the agent market converges on strong performers, the model exchange reprices live, and the upgrade loop and the investing loop push the whole system to keep moving.

### Component map

| Component | Responsibility | Primary tech |
|---|---|---|
| Agent runtime | Defines and executes worker agents, one per service | Agent framework per use case, GCP and OpenAI models, wrapped in Weave |
| Seed agents | The starting roster of distinct specialists | One service each, parameterized from one image |
| Judge | Scores each execution against its subtask | Single LLM call, structured output, Weave traced |
| Broker | Decomposes goals, matches and ranks candidates, hires | Python service, Redis vector search |
| Registry | Hot-path projection of agents, reputation, leaderboard | Redis hashes plus vector index |
| Ledger | Updates reputation and credits, injects model earnings, triggers upgrades | Python module over Postgres + Redis |
| Model Exchange | Lists models as stocks, runs the AMM, prices live | Python module, Postgres (pools) + Redis (hot prices) |
| Investors / Portfolios | Buy and sell model shares, track P&L | Postgres holdings + trades, Redis price reads |
| Simulation layer | OpenAI agents that post tasks and trade, to drive a live demo | OpenAI agent loop, calls the API |
| Event feed | Streams every market event to consumers | `EventBus` port: Redis Stream locally, Pub/Sub in cloud, plus SSE endpoint |
| Dispatch | Sends a hire to the chosen agent's `/run` | `Queue` port: in-process HTTP locally, Cloud Tasks in cloud |
| API layer | Tasks, roster, models, trades, portfolios, feed | FastAPI |
| Persistence | Durable source of truth | Postgres (SQLAlchemy async, Alembic) |
| Observability | Traces every call, renders improvement and market curves | Weave |
| Dashboard | Out of scope for this pass | (deferred) |

---

## 2. Technology Stack

| Layer | Choice | Why |
|---|---|---|
| Agent framework | Decided per use case behind a fixed base class | The base class is the only code bound to it, so the framework can differ per agent without touching the broker or markets |
| Models (workers, broker, judge) | **GCP Gemini Enterprise Agent Platform** (formerly Vertex AI) via the **Google Gen AI SDK** (`google-genai`), plus **OpenAI** models | GCP is the primary compute and gives the model-stock variety (Model Garden: Gemini, Claude, Llama, Gemma, and more). OpenAI models add board variety and power the user simulation |
| Embeddings | GCP text embeddings via `google-genai` (`gemini-embedding-001`) | **GCP only** — the deterministic local-hash fallback is removed. One provider for chat and embeddings. Consequence: local dev now needs GCP credentials for any embedding path (seed, hire). Tests inject a fake. Behind the `Embeddings` port |
| Simulation models | **OpenAI** | The demo's simulated users and investors run as OpenAI agents |
| Durable store | **Postgres** (SQLAlchemy async + Alembic) | Source of truth for users, agents, tasks, the model pools, holdings, trades, and the ledger. Money and ownership need a real database |
| Hot path | **Redis** (vector search, leaderboard, live prices, cache, replay stream) — Docker locally, **Memorystore for Redis 7.2+** in cloud | KNN hiring, live price reads, and the feed must be fast. Redis holds projections rebuildable from Postgres. Present in BOTH environments; Memorystore's native vector search (FLAT KNN, `redis-py`-compatible) covers the index |
| Dispatch | **Google Cloud Tasks** in cloud (HTTP push + OIDC, per-agent queue, retries); in-process HTTP locally — behind the `Queue` port | Reliable, retried, authenticated service-to-service hire dispatch without the broker awaiting the agent inline |
| Event transport | **Pub/Sub** in cloud (fan-out to the SSE feed), **Redis Stream** locally — behind the `EventBus` port | Decoupled event fan-out in cloud; Redis Stream stays as the durable replay log in both envs |
| Backend services | FastAPI in Python | Fast to write, async, native SSE |
| Compute | Cloud Run: one service for the API+broker, one per agent (single parameterized image), Cloud Run Jobs for migrate + seed; all stateless | Stateless services scale to zero between demos; `--min-instances=1` warms the demo |
| Datastores (cloud) | Cloud SQL for PostgreSQL + Memorystore for Redis, reached over a Serverless VPC Access connector; Secret Manager for all secrets | Managed truth + hot path; private IP connectivity; least-privilege per-service service accounts |
| Observability | **Weave** | Host tool, traces every model call and market tick, renders the self-improvement and market curves |
| Build assist | Cursor | Sponsor tool |

**Decisions locked.** Postgres is the durable source of truth and Redis is the hot-path projection rebuildable from it; the earlier "Redis is the only datastore" decision is retired because the model exchange handles money and ownership. The GCP model platform is the Gemini Enterprise Agent Platform (renamed from Vertex AI at Google Cloud Next '26), accessed through the `google-genai` SDK (the old `vertexai` / `google-cloud-aiplatform` SDK is deprecated for Gemini and drops Gemini support after June 2026). OpenAI is a second model provider, used both for some worker agents and for the demo simulation.

**Cloud seam (overturns the earlier "No Pub/Sub" decision).** The previous "no Pub/Sub; the Redis Stream carries all events" decision is **retired**. The system now runs behind a **ports/adapters seam** with one env flag (`RUNTIME_ENV` = `local` | `gcp`). Three ports — `Queue` (hire dispatch), `EventBus` (event publish/subscribe), and `Embeddings` — each have a local adapter and a GCP adapter; the broker, ledger, exchange, API, and sim depend only on the interfaces, never on a Cloud SDK. **Hire dispatch** goes through the `Queue` port: in-process HTTP locally, **Google Cloud Tasks** (HTTP push + OIDC, per-agent queue, retries) in cloud. **Event fan-out** goes through the `EventBus` port: **Redis Stream** locally, **Pub/Sub** in cloud — but **Redis is present in both environments** (Memorystore in cloud) for the hot path (vector index, leaderboard, live prices, cache, and as the durable replay log); Pub/Sub is only the cloud event transport. **Embeddings are GCP-only** (the local-hash fallback is removed). The documented cloud target is Cloud Run (services + jobs) + Cloud SQL + Memorystore + Cloud Tasks + Pub/Sub + Secret Manager + a Serverless VPC Access connector. **Memorystore for Redis 7.2+ supports the vector KNN we need natively** (FLAT, `redis-py`-compatible), so the hot path is unchanged in cloud. The agent framework is left open per use case behind a fixed base class. The frontend dashboard is out of scope for this pass. Full design: see [`docs/cloud-architecture.md`](docs/cloud-architecture.md).

### SDK access patterns

GCP (Gemini Enterprise Agent Platform), chat and embeddings via `google-genai` (>=2.8):

```python
from google import genai
from google.genai import types
client = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)
resp = client.models.generate_content(model="gemini-3.5-flash", contents=prompt)
# Embeddings are GCP-only now (no local fallback). gemini-embedding-001 @ 768 dims;
# manually L2-normalize for any non-3072 dimension.
emb = client.models.embed_content(
    model="gemini-embedding-001", contents=text,
    config=types.EmbedContentConfig(output_dimensionality=768, task_type="RETRIEVAL_DOCUMENT"),
)
```

OpenAI (worker variety and the simulation layer):

```python
from openai import OpenAI
oai = OpenAI()  # OPENAI_API_KEY
resp = oai.responses.create(model="gpt-...", input=prompt)
```

Weave (mandatory tracing, initialized once at startup):

```python
import weave
weave.init("agent-bazaar")  # or "team/agent-bazaar"

@weave.op
def execute(subtask_text, config): ...
```

---

## 3. The Contract (build this first, everything depends on it)

The integration surfaces are the event schema (backend to any consumer), the API contract, and the persistence schema. They live in `contracts/` (Pydantic models for events and core objects) and `contracts/CONTRACTS.md` (the written spec, to be filled in: Redis layout, Postgres tables, API routes). Lock them before writing feature code.

### 3.1 Event feed schema

The server pushes these JSON events onto the `market:feed` stream. Every event also carries `ts` and `event_id`, auto-filled on construction.

Existing agent-market events:

| Event type | Payload fields |
|---|---|
| task_posted | task_id, goal, subtasks (list of {subtask_id, text}) |
| candidates_ranked | subtask_id, candidates (list of {agent_id, match_score, reputation, price, final_score}) |
| agent_hired | subtask_id, agent_id |
| task_executed | subtask_id, agent_id, output_preview |
| task_scored | subtask_id, agent_id, judge_score |
| reputation_changed | agent_id, old, new |
| credits_changed | agent_id, old, new |
| agent_upgraded | agent_id, change_type, detail, cost |

New model-exchange events:

| Event type | Payload fields |
|---|---|
| model_listed | model_id, name, provider (gcp/openai), tier, ipo_price |
| price_changed | model_id, old, new, reason (trade/earnings/tick) |
| earnings_injected | model_id, agent_id, amount, judge_score |
| trade_executed | trade_id, user_id, model_id, side (buy/sell), shares, credits, price |
| portfolio_changed | user_id, credits, holdings_value, total |

Note: `candidates_ranked.price` and `agent_hired` now reflect the **derived** agent price (model stock price times one plus margin), not a stored flat price.

### 3.2 API contract

Existing:

| Method | Path | Purpose | Returns |
|---|---|---|---|
| GET | /agents | Full roster (derived prices included) | list of agent objects |
| POST | /task | Submit a goal, body {goal, user_id?} | {task_id} |
| GET | /feed | SSE stream of all events | text/event-stream |
| POST | /seed | Reset both markets to a fresh state | {ok} |

New (model exchange, investing, users):

| Method | Path | Purpose | Returns |
|---|---|---|---|
| GET | /models | Model board: each stock's price, tier, provider, pool | list of model objects |
| GET | /market | Market snapshot plus recent price history | {models, history} |
| POST | /trade | Buy or sell shares, body {user_id, model_id, side, amount} | {trade_id, price, shares, credits} |
| GET | /portfolio/{user_id} | Holdings, cash, P&L | {credits, holdings, total} |
| POST | /users | Create a user (or sim user) | {user_id} |
| GET | /users | List users / leaderboard by net worth | list |
| POST | /sim/start | Start the OpenAI simulation (task-posters + investors) | {ok} |
| POST | /sim/stop | Stop the simulation | {ok} |

Agent object shape (public roster):

```json
{
  "agent_id": "writer-01",
  "name": "Copywriter",
  "skills": ["writing", "summarization"],
  "capability_text": "Writes and summarizes marketing and technical copy",
  "model": "gemini-3.5-flash",
  "tools": [],
  "reputation": 0.5,
  "credits": 100,
  "margin": 0.2,
  "price": 6.0,
  "hires": 0,
  "wins": 0
}
```

`price` is computed at read time as `model_price(model) * (1 + margin)`; it is not stored.

Model object shape:

```json
{
  "model_id": "gemini-3.5-flash",
  "name": "Gemini 3.5 Flash",
  "provider": "gcp",
  "tier": "flash",
  "price": 12.4,
  "shares": 1000.0,
  "credits": 12400.0,
  "executable": true
}
```

---

## 4. Module Specifications

Each module lists what it does, the tech, how to build it, and what it reads or writes. Build order is in Section 8.

### 4.1 Persistence: Postgres (truth) + Redis (hot path)

What it does: Postgres is the durable source of truth for everything with state or money. Redis holds projections that the hot path needs to be fast: the capability vector index for hiring, the leaderboard, live model prices, and the event stream. Redis is always rebuildable from Postgres by the seeder.

Tech: SQLAlchemy async with `asyncpg`, Alembic migrations, `redis.asyncio` with vector KNN. Locally that is Redis 8 (query engine + vector search in core); in cloud it is Memorystore for Redis 7.2+ (native vector search, FLAT KNN, `redis-py`/dialect-2 compatible — not the third-party module). Cloud connectivity (Cloud SQL Python Connector, Memorystore private IP, VPC connector) is documented in `docs/cloud-architecture.md`.

Postgres tables:

| Table | Holds |
|---|---|
| users | user_id, email, name, password_hash (nullable), credits balance, is_sim flag |
| agents | agent_id, name, skills, capability_text, model (FK to models), tools, margin, reputation, credits, hires, wins, service_url |
| models | model_id, name, provider, tier, executable, pool shares, pool credits, ipo_price |
| tasks | task_id, user_id, goal, status |
| subtasks | task_id, order_index, text, assigned_agent_id, output_preview, judge_score |
| holdings | user_id, model_id, shares |
| trades | user_id, model_id, side, shares, credits, price, created_at |
| ledger_entries | agent_id, task_id, kind (hire/award/upgrade/earnings), credits_delta, reputation_before/after |

Redis keys:

| Structure | Key | Holds |
|---|---|---|
| Hash per agent | agent:{id} | projected agent fields plus capability vector |
| Vector index | agents_idx | KNN over capability vectors |
| Sorted set | leaderboard | agent_id scored by reputation |
| Hash per model | model:{id} | live price, pool shares, pool credits, tier, provider |
| Sorted set | model_prices | model_id scored by current price |
| Stream | market:feed | every event from Section 3.1 |
| Stream | price:history | (optional) price ticks for the market chart |

The agent's stored `price` field is removed; `margin` replaces it. The model pool (`shares`, `credits`) is authoritative in Postgres and projected to Redis for hot reads, and trades update both.

Reads and writes: written by the seeder, ledger, exchange, and trade endpoints; read by the broker and market reads.

### 4.2 Agent Runtime and Base Class

What it does: defines a worker agent and executes a subtask, returning an output. Each agent runs as its own stateless service. Every execution is Weave traced.

Tech: a thin FastAPI wrapper around an agent implementation, a model client (GCP `google-genai` or OpenAI depending on the agent's model), a `@weave.op` on the execute path.

How to build:
- Define one base contract every agent honors regardless of internal framework: `POST /run` taking `{subtask_text, config}` and returning `{output}`. The `config` carries the current model id, margin is not the agent's concern, the tools, and the system prompt.
- The base template handles the HTTP wrapper, config loading, the Weave decorator, and a **model router**: given `config.model`, pick the GCP client or the OpenAI client. This is what lets a single agent be swapped onto any listed model stock.
- Keep agents stateless. All persistent state lives in Postgres and Redis.

Reads and writes: receives config in the request, writes nothing directly.

### 4.2a Agent Service Registry (service URLs)

Unchanged in spirit: `service_url` on each agent record maps `agent_id` to where the broker sends a hire. Localhost ports in dev, Cloud Run URLs after the cutover.

### 4.3 Seed Agents

What it does: the starting roster of 5 to 8 distinct specialists across both providers so the market and the exchange have variety.

How to build:
- Distinct capability profiles (copywriter, code generator, data summarizer, fact checker, translator, planner, and so on), each from the base template.
- Spread agents across model stocks on purpose: some on a GCP flash tier, some on a GCP pro tier, some on an OpenAI model, a couple deliberately weak (a lite model and a vague capability) so the demo shows an agent and its model stock getting starved.
- Equal starting reputation so divergence is earned. Margins spread a little so derived prices differ at the start.
- The seeder writes each agent including `service_url` and capability vector, and ensures every model an agent uses is listed on the exchange.

### 4.4 Broker

What it does: the heart of the agent market. Decomposes a goal, matches and ranks candidates per subtask, hires, dispatches execution, and emits events.

How to build:
- Decompose: one LLM call (GCP model) turns the goal into an ordered subtask list. Emit `task_posted`.
- Match: embed each subtask, KNN against `agents_idx` for top candidates with a match score.
- Rank: `final_score = w_match * match + w_rep * reputation - w_price * derived_price`, where `derived_price = model_price(agent.model) * (1 + agent.margin)`. Weights are fixed constants in config. Emit `candidates_ranked`.
- Hire: pick the top candidate, emit `agent_hired`, read `service_url`, and **dispatch through the `Queue` port** (`queue.enqueue_run(RunDispatch(...))`) instead of calling the agent inline. Locally the `Queue` adapter does an in-process HTTP `POST /run`; in cloud it enqueues a **Cloud Tasks** HTTP-push task (OIDC, per-agent queue, retries). The broker does **not** await the model output here.
- Result handling: the agent's output returns via a shared `handle_run_result(subtask_id, agent_id, output)` path — directly in the local adapter, or via the agent's OIDC result callback to `/internal/runs/result` in cloud. `handle_run_result` emits `task_executed`, runs the judge, and hands off to the ledger. It is idempotent on `subtask_id` so a Cloud Tasks retry is safe.

Because the price term reads the live model stock, the broker's choices shift as the exchange moves, with no broker code change. Because dispatch is behind the `Queue` port, the local↔cloud cutover is an adapter swap (env flag), not a broker change. See [`docs/cloud-architecture.md`](docs/cloud-architecture.md) §3–§4.

### 4.5 Judge

Unchanged: a single GCP LLM call with structured output, Weave traced, scoring the output against the subtask from 0 to 1 with a one line reason. Emit `task_scored`. Force JSON so parsing never breaks the loop.

### 4.6 Ledger (reputation, credits, earnings)

What it does: turns a judge score into updated reputation and credits for the agent, **and into earnings injected onto the agent's model stock**, and decides when an agent can upgrade.

How to build:
- Reputation: EMA, `new = alpha * score + (1 - alpha) * old`, alpha around 0.3. Update the leaderboard. Emit `reputation_changed`.
- Credits: award the agent credits proportional to the judge score and its derived price (it earned its fee). Emit `credits_changed`.
- **Earnings to the model stock:** inject `earnings = earn_rate * (judge_score - 0.5) * hire_weight` into the agent's model pool (positive for good scores, negative for bad). This is the fundamentals signal that moves the stock independent of trading. Hand off to the exchange (4.8a) to apply it and emit `earnings_injected` and `price_changed`.
- Increment `hires` and `wins`. After updates, check the upgrade threshold and hand to the upgrade module.

Reads and writes: reads and writes agent and model rows and the leaderboard, writes ledger entries and events.

### 4.7 Upgrade Logic

What it does: when an agent crosses the credit threshold it spends credits to improve. With derived pricing, the upgrade options change.

How to build:
- Pick an upgrade: **raise margin** (charge more because it is in demand), **swap model stock** (move to a stronger or cheaper-but-rising model, which re-points the agent's `model` and changes its derived price and its future earnings target), or **add a tool**.
- Apply as a config change in Postgres and the Redis projection, not a redeploy. The agent service reads model and tools from the request config each call, so an upgrade takes effect on the next hire.
- Deduct the cost from credits. If capability changes, update `capability_text` and re-embed. Emit `agent_upgraded`.
- Keep agent creation and mutation in one function so gap-driven synthesis can reuse it later.

The clean demo beat: an agent earns its way to a model swap onto a hot stock, climbs the leaderboard faster, and investors who bought that model stock profit.

### 4.8 Event Feed and Streaming

Every module (broker, ledger, exchange, trade endpoint, sim) emits through one `EventBus` port: `event_bus.publish(event)`. The `/feed` endpoint forwards events as server-sent events via `event_bus.subscribe(...)`.

- **Local (`RUNTIME_ENV=local`):** the `EventBus` adapter is the Redis Stream — `publish` is `XADD market:feed`, `subscribe` is the `XREAD` loop. The stream is the durable replay log (`from_id="0"` replays).
- **Cloud (`RUNTIME_ENV=gcp`):** the adapter publishes to a **Pub/Sub** topic (`market-feed`) for live fan-out **and** dual-writes `XADD market:feed` to Memorystore as the durable replay log. The API holds a Pub/Sub pull subscription and an in-process broadcaster that fans events to all connected SSE clients. For the demo the API runs single-instance so one subscription serves all clients; see [`docs/cloud-architecture.md`](docs/cloud-architecture.md) §5 for the multi-instance pattern.

The event schema (§3.1) is identical in both environments; only the transport changes.

### 4.8a Model Exchange (the AMM)

What it does: lists each model as a stock and prices it live. This is the new headline.

Tech: a Python module over the model pools (Postgres authoritative, Redis projection), a constant-product automated market maker, Weave traced ticks.

How to build:
- Each model has a pool `(shares S, credits C)` with `price = C / S` and invariant `k = S * C`.
- **Listing (IPO):** set the initial price by tier (pro highest, then flash, then lite), choose an initial share count, set `C = price0 * S`, record `k`. Emit `model_listed`.
- **Buy:** investor spends `dc` credits, `C' = C + dc`, `S' = k / C'`, shares received `= S - S'`, price rises. **Sell:** investor returns `ds` shares, `S' = S + ds`, `C' = k / S'`, credits returned `= C - C'`, price falls. Both update Postgres and Redis and emit `trade_executed` and `price_changed`.
- **Earnings injection (fundamentals):** when the ledger reports earnings for a model, add the amount to `C` (and recompute `k = S * C`) without issuing shares. Positive earnings lift the price and reward holders; negative earnings bleed it. Emit `earnings_injected` and `price_changed`.
- Keep all rates and tier base prices as fixed constants in config (no tuning UI).

Reads and writes: reads and writes model pools in Postgres and Redis, writes events. Called by the ledger (earnings) and the trade endpoint (buys and sells).

### 4.9 Investors and Portfolios

What it does: lets users hold positions in model stocks and tracks their wealth. In the real product these are people; in the demo they are simulated OpenAI agents.

How to build:
- A user has a credit balance. `POST /trade` routes a buy or sell through the exchange (4.8a), debits or credits the user's balance, and updates `holdings`.
- Portfolio value `= credits + sum(shares * current model price)`. `GET /portfolio/{user_id}` returns cash, positions, and total. Emit `portfolio_changed` after a trade.
- Record every trade in `trades` for P&L and for the demo's investor leaderboard.

Reads and writes: reads model prices, writes users, holdings, trades; emits events.

### 4.10 Simulation Layer

What it does: makes both markets live without humans, so the demo runs itself. **No static mockups** are used; the market is driven by real LLM-agent behavior against the real API.

Tech: OpenAI agents in a loop, calling the public API.

How to build:
- **Task-poster sims:** OpenAI agents that generate varied, realistic goals and `POST /task`, so the agent market keeps running. This replaces the old static mock event file.
- **Investor sims:** OpenAI agents that read `/market` and `/feed`, reason about which models the winning agents use, and `POST /trade` to buy or sell. Their flows move prices through the AMM.
- Drive intensity and cadence with simple parameters. `POST /sim/start` and `POST /sim/stop` control the run. Every sim decision is a `@weave.op` so the simulation itself is traceable.

Reads and writes: calls the API only; writes nothing directly.

### 4.11 Observability (Weave)

What it does: traces every model call and every market tick, and renders the curves that prove the system improves and the exchange is alive.

How to build:
- `weave.init` once at service start.
- `@weave.op` on every LLM-calling function: broker decompose, broker match and rank, agent execute, judge score, and every sim agent decision. Trace inputs, outputs, model, latency, and cost.
- Treat exchange operations as ops too (earnings injection, trades) so price moves are traceable to their cause.
- Custom metrics per task: judge score, cost, which agent and which model, the model's price before and after. Build Weave views for: rolling success rate, cost per task, per-model price history, and investor portfolio returns.
- Mandatory regardless of anything else, it is the host tool and how the demo lands.

---

## 5. Data Flow

### One task, end to end

1. A user (or task-poster sim) `POST /task`. API stores the task, returns the id, kicks the broker.
2. Broker decomposes, emits `task_posted`.
3. Per subtask: broker embeds it (GCP embeddings), KNN against `agents_idx`, ranks by match plus reputation minus **derived price**, emits `candidates_ranked`, hires the top, emits `agent_hired`.
4. Broker dispatches the hire through the `Queue` port (in-process HTTP locally, Cloud Tasks push in cloud). The agent executes on its model (GCP or OpenAI); its output returns via `handle_run_result` (directly locally, or via an OIDC result callback in cloud), which emits `task_executed`.
5. Judge scores, emits `task_scored`.
6. Ledger updates reputation and credits, **injects earnings into the agent's model stock**, emits `reputation_changed`, `credits_changed`, `earnings_injected`, and `price_changed`.
7. If the credit threshold is crossed, upgrade runs (margin, model swap, or tool), emits `agent_upgraded`.

### One trade, end to end

1. A user (or investor sim) `POST /trade {user_id, model_id, side, amount}`.
2. The exchange applies the AMM (buy or sell), updates the model pool in Postgres and Redis, updates the user's balance and holdings.
3. Emits `trade_executed`, `price_changed`, and `portfolio_changed`.
4. Because agent price is derived from model price, the next `candidates_ranked` reflects the new price with no broker change.

All events flow through the `EventBus` port to `/feed` (Redis Stream locally, Pub/Sub + Redis Stream replay in cloud). Weave records every model call and every exchange operation.

---

## 6. Cloud and Deployment (GCP)

The full end-to-end cloud design — topology diagram, port interface signatures, dispatch and
event flows, IAM, deploy commands, versions, and open questions — lives in
[`docs/cloud-architecture.md`](docs/cloud-architecture.md). Summary:

| Concern | Service | Notes |
|---|---|---|
| API and broker | Cloud Run (`api-broker`) | One stateless service; enqueues hires, bridges Pub/Sub → SSE `/feed`; `--min-instances=1` for the demo |
| Agent execution | Cloud Run, one service per agent (`agent-<id>`) | One parameterized image; invoked via Cloud Tasks OIDC push; deployed `--no-allow-unauthenticated` |
| Migrate / seed | Cloud Run **Jobs** (`migrate`, `seed`) | `alembic upgrade head`; seed both markets. Jobs run to completion |
| Hire dispatch | **Cloud Tasks** (one queue per agent) | HTTP push + OIDC, built-in retries/backoff, dedup by task name. `Queue` port |
| Event fan-out | **Pub/Sub** (topic `market-feed`, pull sub) | Feeds the SSE bridge; Redis Stream kept as the replay log. `EventBus` port |
| GCP models and embeddings | Gemini Enterprise Agent Platform via `google-genai` | Chat for agents, judge, decompose; **GCP-only** embeddings (`gemini-embedding-001`) for matching |
| OpenAI models | OpenAI API | Worker variety and the simulation layer |
| Durable store | **Cloud SQL for PostgreSQL 16** (Docker Postgres locally) | Source of truth; reached via the Cloud SQL Python Connector (private IP) |
| Hot path | **Memorystore for Redis 7.2+** (Docker Redis 8 locally) | Vector index (native FLAT KNN, `redis-py`-compatible), leaderboard, live prices, cache, replay stream |
| Networking | Serverless VPC Access connector | Cloud Run → Cloud SQL / Memorystore private IP |
| Secrets | Secret Manager | `DATABASE_URL`, `REDIS_URL`, `OPENAI_API_KEY`, `WANDB_API_KEY` (GCP creds via the attached service account) |
| Images | Artifact Registry | `api` and the single parameterized `agent` image |

**Memorystore vector note:** Memorystore for Redis 7.2+ provides vector search **natively in
the engine** (FLAT + HNSW) via `FT.CREATE`/`FT.SEARCH` that are command-compatible with
`redis-py` (dialect 2). It is not the third-party RediSearch module, but the FLAT KNN over a
HASH index that the registry uses is fully supported — so the hot path needs no change in
cloud. Fallbacks (Redis Cloud/Enterprise on Marketplace, or self-hosted Redis 8) are `REDIS_URL`-only swaps. See `docs/cloud-architecture.md` §9.

Local development runs Postgres and Redis in Docker (`docker compose up -d postgres redis`),
migrates with Alembic, seeds both markets, and runs agents on localhost ports
(`RUNTIME_ENV=local`). Because embeddings are GCP-only now, **local dev needs GCP credentials**
(ADC + `GCP_PROJECT`/`GCP_LOCATION`) for any embedding path. The cloud cutover is an adapter
swap (`RUNTIME_ENV=gcp`) plus repointing each agent `service_url` to its Cloud Run URL — the
broker only knows the URL, so nothing in the broker changes. Warm the demo agents
(`--min-instances=1`) before presenting to avoid cold starts.

---

## 7. Demo Flow

1. Hit `/seed`. Fresh agent roster, all reputations equal; every model listed at its tier IPO price; sim users funded with starting credits.
2. `POST /sim/start`. OpenAI task-poster agents fire varied goals; OpenAI investor agents begin trading.
3. Agent reputations diverge live. A weak agent stops getting hired and its model stock stops earning.
4. A strong agent crosses the credit threshold and swaps onto a hot model stock; it climbs faster.
5. The model exchange reprices live: stocks of models the winning agents use rise on earnings and on investor buying; investor portfolios that backed them grow.
6. Cut to Weave: rolling success rate rising, cost per task falling, model price history, and investor returns, all across the same task stream.

The story in about 90 seconds: the agent market improves, agents improve, the model exchange is alive and investable, and Weave proves all of it with numbers.

---

## 8. Build Order (solo, sequential)

Phases run in order. Each phase ends at a runnable, testable checkpoint. The core broker and worker loop is built first; the exchange, investing, and simulation layer build on top.

### Phase 0: contracts (done / finalize)
Lock the event schema (3.1), API contract (3.2), and persistence schema (4.1). Fill in `contracts/CONTRACTS.md`. Add the new events and the `models`, `holdings`, `trades` shapes; replace agent `price` with `margin`. **Already mostly built:** Pydantic schemas and events, infra (config, async Postgres, Redis, embeddings), DB models and repo, Alembic init, registry, feed, seeder, smoke test.

### Phase 1: persistence and migrations update
Add `models`, `holdings`, `trades`; add `credits` and `is_sim` to users; add `margin` to agents and a model FK; drop the stored agent `price`. New Alembic revision. Update the seeder to list models and seed sim users. Update embeddings from the deprecated `vertexai` SDK to `google-genai`.

### Phase 2: the agent loop (core)
Agent base template with the GCP/OpenAI model router (4.2), seed agents across both providers (4.3), judge (4.5), broker decompose/match/rank/hire over HTTP (4.4), with **derived pricing reading a placeholder fixed model price** so the loop runs before the exchange exists. Weave on every LLM call (4.11). Checkpoint: one task runs end to end and is scored.

### Phase 3: ledger and the model exchange
Ledger reputation and credits (4.6). Model Exchange AMM: listing, buy, sell, earnings injection (4.8a). Wire the ledger's earnings into the exchange and switch the broker's derived price to read the live model stock. Checkpoint: tasks move reputation and credits, and model prices move on earnings.

### Phase 4: investing and users
`/trade`, `/portfolio`, `/users` (4.9), holdings and trades, portfolio P&L. Checkpoint: a user can buy a model stock, prices move, and the portfolio revalues.

### Phase 5: simulation layer
OpenAI task-poster and investor sims (4.10), `/sim/start` and `/sim/stop`. Checkpoint: with one button the whole system runs live with no human input.

### Phase 6: Weave curves and upgrade
Upgrade logic (4.7: margin, model swap, tool). Weave custom views for success rate, cost per task, price history, and investor returns (4.11). Checkpoint: the full demo story runs.

### Cloud cutover (near the end)
Build the GCP adapters (`Queue`→Cloud Tasks, `EventBus`→Pub/Sub, the Cloud SQL connector wiring) behind the ports, then set `RUNTIME_ENV=gcp`, provision the infra (Artifact Registry, Cloud Run services/jobs, per-agent Cloud Tasks queues, Pub/Sub topic+subscription, Cloud SQL + Memorystore over a VPC connector, Secret Manager, IAM), and repoint each `service_url` from localhost to its Cloud Run URL. The broker only knows the URL and the `Queue` port, so nothing in the broker changes. The build plan threads this through the branches and adds a dedicated `feat/cloud-infra` branch — see [`docs/cloud-architecture.md`](docs/cloud-architecture.md) and `docs/plans/backend-plan.md`.

### Stretch: gap-driven synthesis (only if ahead)
A meta-agent watches for subtasks where the best candidate's match score is below a floor, then calls the same agent-creation function the upgrade module uses to spin up a new specialist (and list its model if new). Additive, not a rewrite.

---

## 9. Risk Notes

| Risk | Mitigation |
|---|---|
| Two economies are hard to tune | Keep all weights, the reputation alpha, the AMM earn rate, and tier base prices as fixed constants. No tuning UI |
| AMM math edge cases (divide by zero, negative pool) | Floor pool credits and shares above zero, clamp earnings, reject trades that would empty a pool |
| Derived price feedback oscillates | Conservative `w_price` and earn rate; mean behavior is dampened by the EMA reputation and small earnings steps |
| SDK migration (Vertex to Gen AI SDK) | Use `google-genai` from the start; verify the `embed_content` response shape against the installed version. **Embeddings are GCP-only** — local dev needs GCP credentials; offline tests inject a `FakeEmbeddings` (no production local-hash path) |
| Two model providers double the surface | One model-router behind the agent base class; provider is just a field on the model stock |
| Per-agent Cloud Run cold start | Warm the demo agents with `--min-instances=1`, develop against localhost, treat deploy as an adapter swap (`RUNTIME_ENV`) |
| Memorystore vector support | Verified: Memorystore for Redis 7.2+ has native FLAT KNN, `redis-py`-compatible. Fallbacks (Redis Cloud/Enterprise, self-hosted Redis 8) are `REDIS_URL`-only swaps. See `docs/cloud-architecture.md` §9 |
| Cloud Tasks dispatch is async (no inline output) | Output returns via an idempotent `handle_run_result` (direct locally, OIDC callback in cloud); dedup by task name + per-subtask idempotency |
| Judge inconsistency breaks the curve | Force structured output, short fixed judge prompt |
| Sim agents behave erratically and break the demo | Constrain sim prompts and cadence, cap trade sizes, keep `/seed` for a clean reset and the stream as a replay log |
| Solo bandwidth | Strict phase order; each phase is independently runnable so progress is always demoable |
```
