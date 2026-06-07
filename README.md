# Anex

A self-organizing agent marketplace fused with a live model exchange. Worker agents advertise tiered capabilities; a broker decomposes incoming goals into subtasks, recalls candidates by embedding similarity, re-ranks finalists with an LLM, and dispatches work. A judge scores outputs; the ledger updates reputation and credits; users trade model-stock on a constant-product AMM. Good agents get hired more, earn credits, and the market converges on strong performers.

Built for WeaveHacks 4 (Multi-Agent Orchestration).

## The loop

1. User (or sim poster) posts a goal → broker decomposes → vector recall → LLM re-rank → hire → agent executes.
2. Judge scores the output → ledger settles reputation/credits → model earnings hit the AMM → events stream on `/feed`.
3. Investors trade model shares; prices move on the curve; portfolio value reflects holdings + credits.

## Repository layout

| Path | Role |
|------|------|
| `contracts/` | Shared event schemas, API types, Redis key conventions |
| `backend/agent/` | Generic worker pool (FastAPI services on ports 9001+) |
| `backend/market/` | Registry, broker, judge, ledger, exchange, seeder, capabilities catalog |
| `backend/sim/` | OpenAI-driven poster/investor simulation loops |
| `backend/api/` | FastAPI app (`app.py`), task concurrency pool, SSE feed |
| `frontend/` | Live trading-floor dashboard (Next.js) |

Specialist agents are defined in `backend/market/data/capabilities.json` (pro / flash / lite tiers per capability family). At seed time they register in Postgres/Redis; execution routes through a **shared worker pool** — the broker passes model config per dispatch, so any worker can run any agent.

## Stack

GCP Gemini Enterprise Agent Platform (embeddings + broker/judge chat), OpenAI (sim variety), Redis 8 (registry, vector index, feed stream), Postgres 16 (system of record), FastAPI, Weave tracing.

## Quick start

### 1. Datastores

```bash
docker compose up -d postgres redis
pip install -r requirements.txt
```

Create a `.env` at the repo root with at least:

```bash
GCP_PROJECT=your-gcp-project-id
GCP_LOCATION=global
OPENAI_API_KEY=sk-...          # required for simulation loops
```

Local seeding and hiring call real GCP embeddings (`gemini-embedding-001` @ 768 dims). Use Application Default Credentials or `GOOGLE_APPLICATION_CREDENTIALS`.

```bash
alembic upgrade head
export GCP_PROJECT=your-gcp-project-id GCP_LOCATION=global
python -m backend.market.seeder
python -m tests.0001_init
```

Use `EMBEDDINGS_FAKE=1` only for offline smoke runs (vectors won't match a real index).

### 2. Worker pool + API

**All-in-one (API + workers):**

```bash
./start.sh
```

**Or run separately:**

```bash
./scripts/run_agents.sh    # 16 generic workers on :9001–:9016 (override with AGENT_WORKERS)
uvicorn backend.api.app:app --host 0.0.0.0 --port 8000 --reload
```

Or: `docker compose --profile api up -d api`

Defaults: **16 workers**, **119 tiered seed agents** in the registry (from `capabilities.json`).

### 3. Frontend (optional)

```bash
cd frontend && npm install && npm run dev
```

Set `NEXT_PUBLIC_API_URL=http://localhost:8000` if the API is not on the default host.

## Simulation

**Unit tests** (no live OpenAI):

```bash
EMBEDDINGS_FAKE=1 WEAVE_DISABLED=1 pytest tests/test_sim_decision.py -v
```

**Light in-process demo** (loops run inside uvicorn — fine for a few sim users):

```bash
curl -X POST http://localhost:8000/sim/start
curl -X POST http://localhost:8000/sim/stop
```

**Heavy load — external sim runner (recommended):**

Run sim loops in a **separate process** so poster/investor HTTP traffic and OpenAI calls don't contend with the API event loop:

```bash
./scripts/run_sim.sh
# or
python -m backend.sim.main --posters 10 --investors 15 --cadence-s 5
```

The runner calls the same HTTP API (`API_URL`, default `http://localhost:8000`), creates `sim-poster-*` / `sim-investor-*` users, and respects broker backpressure via `GET /task/slots`.

## Concurrency knobs

| Variable | Default | Purpose |
|----------|---------|---------|
| `MAX_CONCURRENT_TASKS` | `2` | Semaphore cap on concurrent broker pipelines (`POST /task`) |
| `AGENT_WORKERS` | `16` | Generic worker processes in the pool |
| `AGENT_WORKER_BASE_PORT` | `9001` | First worker port |
| `RANK_RECALL_K` | `10` | Vector recall breadth before LLM re-rank |
| `RERANK_FINALISTS` | `6` | Finalists passed to the hiring LLM |
| `SIM_POSTERS` | `2` | Default poster sim users |
| `SIM_USE_COHORTS` | `1` | Role-based hybrid investors (math mm/quant + LLM retail/whale) |
| `SIM_MM_COUNT` / `SIM_MM_CADENCE_S` | `8` / `3` | Market-maker cohort (math) |
| `SIM_QUANT_COUNT` / `SIM_QUANT_CADENCE_S` | `6` / `6` | Quant cohort (math) |
| `SIM_RETAIL_COUNT` / `SIM_RETAIL_CADENCE_S` | `20` / `12` | Retail cohort (LLM) |
| `SIM_WHALE_COUNT` / `SIM_WHALE_CADENCE_S` | `4` / `30` | Whale cohort (LLM, larger trades) |
| `SIM_WHALE_TRADE_CAP` | `250` | Max trade size for whale investors |
| `SIM_INVESTORS` | `8` | Legacy mode only (`SIM_USE_COHORTS=0`) |
| `SIM_INVESTOR_MODE` | `llm` | Legacy mode only: `llm` or `math` for all investors |
| `SIM_CADENCE_S` | `4.0` | Poster loop cadence; legacy investor cadence |
| `TRADE_CAP` | `100` | Max credits/shares per sim trade (non-whale) |
| `POSTER_BUDGET_CAP` | `150` | Sim poster task budget cap |
| `API_URL` | `http://localhost:8000` | Base URL for sim runner and agents |

### Market dynamics

The exchange keeps a **tradable mid** (`P = credits/shares` on the constant-product AMM) separate from a **fundamental fair value** `F` (moved by judge scores). A background **arb kernel** mean-reverts `P` toward `F` with tier-scaled volatility. Bid/ask quotes are derived from small-trade AMM slippage.

| Variable | Default | Purpose |
|----------|---------|---------|
| `EARN_BASELINE` | `0.62` | Judge score break-even for fundamentals |
| `EARN_RATE` | `8.0` | Earnings sensitivity per scored subtask |
| `POOL_PASS_THROUGH` | `0.35` | Fraction of earnings that hit the AMM pool |
| `FUNDAMENTAL_SCALE` | `5000` | Fundamental log-return scaling |
| `ARB_INTERVAL_S` | `2.0` | Seconds between arb ticks |
| `ARB_MAX_BPS` | `15` | Max per-tick arb move (basis points) |
| `KAPPA_PRO/FLASH/LITE` | — | Mean-reversion speed per tier |
| `SIGMA_PRO/FLASH/LITE` | — | Exogenous volatility per tier |
| `QUOTE_SIZE` | `10` | Credits notional for bid/ask quotes |
| `HISTORY_PER_MODEL` | `2000` | Per-model price history cap |

Dev scripts:

```bash
./scripts/reset_fresh.sh           # wipe + IPO seed
./scripts/seed_market_snapshot.sh  # GBM history + varied board
```

Under load, sync LLM calls (decompose, judge, sim goals/trades) run in thread pools; Redis and sim HTTP calls retry transient failures with backoff.

## Weave tracing

Set `WEAVE_PROJECT=anex` (or any project name you prefer). Disable locally with `WEAVE_DISABLED=1` (pytest sets this automatically).

Broker, judge, and sim ops are decorated with `@weave.op`.

## Testing

Full offline suite:

```bash
EMBEDDINGS_FAKE=1 WEAVE_DISABLED=1 pytest -v
```

Focused suites:

```bash
pytest tests/0003_agent_loop.py -v       # broker rank / decompose
pytest tests/0004_amm.py -v            # exchange curve
pytest tests/0005_ledger.py -v         # reputation settlement
pytest tests/0006_trading.py -v        # user trading
pytest tests/0006_credits_auth.py -v   # credits + auth
pytest tests/test_concurrency.py -v    # task cap, retries
pytest tests/test_sim_decision.py -v   # sim JSON parsing
pytest tests/0007_market_dynamics.py -v  # fundamentals, quotes, GBM, arb
```

## Further reading

- `build_doc.md` — product spec and build phases
- `docs/cloud-architecture.md` — GCP deployment design
- `docs/plans/backend-plan.md` — implementation plan
- `model_use.md` — GCP model endpoint notes
