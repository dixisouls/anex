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
| `SIM_INVESTORS` | `8` | Default investor sim users |
| `SIM_CADENCE_S` | `4.0` | Seconds between each sim user's loop iteration |
| `TRADE_CAP` | `100` | Max credits/shares per sim trade |
| `API_URL` | `http://localhost:8000` | Base URL for sim runner and agents |

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
```

## Further reading

- `build_doc.md` — product spec and build phases
- `docs/cloud-architecture.md` — GCP deployment design
- `docs/plans/backend-plan.md` — implementation plan
- `model_use.md` — GCP model endpoint notes
