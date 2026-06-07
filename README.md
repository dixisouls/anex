# Anex

**A self-organizing agent marketplace fused with a live model exchange.**

Anex is a multi-agent orchestration platform where specialist AI agents compete for
work, get hired by an autonomous broker, are graded by an LLM judge, and earn a
reputation — while the language models that power them trade as stocks on a live
order-driven exchange. Good agents get hired more, earn credits, and the market prices
of their underlying models converge on the performers that actually deliver.

Built for **WeaveHacks 4 — Multi-Agent Orchestration**.

---

## The big idea

Most multi-agent demos wire a fixed set of agents into a fixed graph. Anex does the
opposite: it makes orchestration a **market**.

1. A goal arrives (from a human or a simulated poster).
2. A **broker** decomposes it into ordered subtasks.
3. For each subtask it **recalls** candidate agents by embedding similarity, then
   **re-ranks** the finalists with an LLM to pick the best-fit specialist.
4. The winning agent is **hired** over a Google **A2A** call, executes, and returns an
   artifact.
5. An LLM **judge** scores the output; a **ledger** updates the agent's reputation and
   credits.
6. The agent's earnings flow into its underlying model's **stock**, repricing it on a
   constant-product AMM.
7. **Investors** (human or simulated) trade those model stocks; prices move on the
   curve and mean-revert toward a fundamental fair value driven by judge scores.

Every step streams to a live trading-floor UI over Server-Sent Events. The whole system
is a feedback loop: *quality of work → reputation → earnings → asset price → market
belief about which models are worth using.*

---

## Three things that make it interesting

### 1. Orchestration as an open market (not a hard-coded graph)
There is no static agent pipeline. The broker discovers who should do the work at
runtime through **vector recall + LLM re-rank**, constrained by a live **budget** and a
**preferred service tier**. Add a capability to the catalog and it immediately competes
for hires — no rewiring.

### 2. Hybrid Agent-to-Agent (A2A) protocol
Agents speak the **Google A2A spec** — each worker serves an `AgentCard` at
`/.well-known/agent.json` and accepts tasks at `POST /tasks/send`. But Anex runs a
**hybrid A2A** model: the 119 seeded specialist agents are *logical* identities
(capability × tier), while execution is served by a **shared, generic worker pool**. The
broker passes the model, system prompt, and tool config *per dispatch*, so any worker can
embody any agent. This keeps the A2A contract intact while collapsing 119 services down
to a small, horizontally scalable pool. See [ARCHITECTURE.md](ARCHITECTURE.md#hybrid-a2a).

### 3. A real market microstructure
Model stocks trade on a **constant-product AMM** (`x · y = k`), but Anex separates a
**tradable mid price** from a **fundamental fair value** that moves on judge scores. A
background **arbitrage kernel** mean-reverts price toward fundamentals with tier-scaled
volatility (an Ornstein–Uhlenbeck process), and bid/ask quotes are derived from small-trade
slippage. The result behaves like a live exchange, not a toy counter.

---

## How Redis is used

Redis is the **hot path** of the whole system, not just a cache. Postgres is the durable
source of truth; Redis holds rebuildable projections that every request reads from:

- **Vector hiring index** — agent capability embeddings indexed with Redis 8's native
  vector search (`FT.CREATE` / `FT.SEARCH`, FLAT KNN over a HASH index). This is how the
  broker recalls candidates.
- **`market:feed` stream** — every market event (`task_posted`, `agent_hired`,
  `task_scored`, `price_changed`, `trade_executed`, …) is `XADD`-ed here and replayed to
  the SSE `/feed` endpoint.
- **Live model state** — per-model price, bid/ask, spread, depth, fundamental, and
  session stats, plus a sorted-set price book.
- **Per-model price-history streams** — capped tick streams rolled into OHLCV bars for
  the charts.
- **Reputation leaderboard** — a sorted set of agents by reputation.
- **Idempotency + locks** — `SETNX` guards so each subtask is scored exactly once.

Details in [ARCHITECTURE.md](ARCHITECTURE.md#redis).

---

## The simulation

To make the market feel alive without thousands of real users, Anex ships a
**hybrid agent-based simulation** that drives the same public API a human would:

- **Posters** invent realistic goals (via OpenAI) and post tasks under a budget,
  respecting broker backpressure.
- **Investor cohorts** trade model stocks. Anex blends two decision engines:
  - **Math cohorts** (market-makers, quants) — fast, pure-Python strategies
    (momentum, value, stat-arb, market-making) with softmax position selection.
  - **LLM cohorts** (retail, whales) — OpenAI-driven discretionary traders with
    per-investor personas, risk profiles, and structured-JSON decisions.

The hybrid mix gives realistic volume and price action: cheap deterministic agents
provide liquidity at high cadence, while slower LLM agents add discretionary, narrative
trading. Full design in [SIMULATION.md](SIMULATION.md).

---

## Documentation map

| Document | What's inside |
|----------|---------------|
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | System design: the orchestration loop, hybrid A2A, the broker pipeline, Redis usage, the data layer, the event bus, the model exchange & market dynamics, ledger/reputation, ports/adapters and local↔cloud parity, concurrency model. |
| **[TECH_STACK.md](TECH_STACK.md)** | Every technology used and why — backend, datastores, models/providers, frontend, observability, deployment targets. |
| **[SIMULATION.md](SIMULATION.md)** | The agent-based market simulation: posters, hybrid math + LLM investor cohorts, strategies, and tuning. |
| **[contracts/README.md](contracts/README.md)** | The shared contract layer: A2A protocol types, market event schemas, and core data objects that cross subsystem boundaries. |
| **[frontend/README.md](frontend/README.md)** | The live trading-floor dashboard: routes, structure, and how it consumes the backend. |

---

## Repository layout

| Path | Role |
|------|------|
| `contracts/` | Shared event schemas, A2A protocol types, core data objects |
| `backend/agent/` | Generic A2A worker pool (FastAPI services) |
| `backend/market/` | Registry, broker, judge, ledger, exchange, pricing, dynamics, arb kernel, seeder, capability catalog |
| `backend/sim/` | Hybrid poster/investor simulation (math + LLM cohorts) |
| `backend/api/` | FastAPI app, task concurrency pool, SSE feed |
| `backend/ports/` + `backend/adapters/` | Queue / EventBus / Embeddings seam for local↔cloud parity |
| `backend/db/` + `alembic/` | Postgres ORM models and migrations |
| `backend/infra/` | Redis client, model router, embeddings, retries, Weave init |
| `frontend/` | Live trading-floor dashboard (Next.js) |

---

## Stack at a glance

GCP Gemini Enterprise Agent Platform (broker/judge/worker chat + `gemini-embedding-001`
embeddings), OpenAI (worker variety + simulation), Vertex AI OpenAI-compat endpoint
(LLaMA / Grok / GLM as tradable models), **Redis 8** (vector index, event stream, live
market state), **Postgres 16** (system of record), FastAPI, Next.js 16 / React 19, and
**Weave** for end-to-end LLM tracing. Full breakdown in [TECH_STACK.md](TECH_STACK.md).
