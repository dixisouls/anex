# Agent Bazaar

A self-organizing agent marketplace. Worker agents advertise capabilities; a broker decomposes incoming goals into subtasks, matches agents by embedding similarity, ranks by fit + reputation − price, and dispatches work. A judge scores outputs; the ledger updates reputation and credits; users trade model-stock on a constant-product AMM. Good agents get hired more, earn credits, and the market converges on strong performers.

Built for WeaveHacks 4 (Multi-Agent Orchestration).

## The loop

1. User (or sim poster) posts a goal → broker decomposes → vector search → rank → hire → agent executes.
2. Judge scores the output → ledger settles reputation/credits → events stream on `/feed`.
3. Investors trade model shares; prices move on the AMM; portfolio value reflects holdings + credits.

## Repository layout

| Path | Role |
|------|------|
| `contracts/` | Shared event schemas, API types, Redis key conventions |
| `backend/agent/` | Stateless worker agent services (ports 9001–9006) |
| `backend/market/` | Registry, broker, judge, ledger, exchange, seeder |
| `backend/sim/` | OpenAI-driven poster/investor simulation loops |
| `backend/api/` | FastAPI app (`app.py`), task concurrency pool |
| `frontend/` | Live trading-floor dashboard (Next.js, CopilotKit) |

## Stack

GCP Gemini (embeddings + broker/judge chat), OpenAI (sim variety), Redis (registry, vector index, feed stream), Postgres (system of record), FastAPI, Weave tracing.

## Quick start

### 1. Datastores

```bash
docker compose up -d postgres redis
pip install -r requirements.txt
cp .env.example .env   # set GCP_PROJECT, OPENAI_API_KEY as needed
alembic upgrade head
```

### 2. Seed market + verify

```bash
export GCP_PROJECT=your-project GCP_LOCATION=global
python -m backend.market.seeder
python -m tests.0001_init
```

Use `EMBEDDINGS_FAKE=1` only for offline smoke runs (vectors won't match a real index).

### 3. Worker agents

```bash
./scripts/run_agents.sh
```

Six seed agents on ports 9001–9006.

### 4. API

```bash
uvicorn backend.api.app:app --host 0.0.0.0 --port 8000 --reload
```

Or: `docker compose --profile api up -d api`

### 5. Frontend (optional)

```bash
cd frontend && npm install && npm run dev
```

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
| `SIM_POSTERS` | `2` | Default poster sim users |
| `SIM_INVESTORS` | `3` | Default investor sim users |
| `SIM_CADENCE_S` | `8.0` | Seconds between each sim user's loop iteration |
| `TRADE_CAP` | `100` | Max credits/shares per sim trade |
| `API_URL` | `http://localhost:8000` | Base URL for sim runner and agents |

Under load, sync LLM calls (decompose, judge, sim goals/trades) run in thread pools; Redis and sim HTTP calls retry transient failures with backoff.

## Weave tracing

Set `WEAVE_PROJECT=agent-bazaar` (default). Disable locally with `WEAVE_DISABLED=1` (pytest sets this automatically).

Broker, judge, and sim ops are decorated with `@weave.op`.

## Testing

Full offline suite:

```bash
EMBEDDINGS_FAKE=1 WEAVE_DISABLED=1 pytest -v
```

Focused suites:

```bash
pytest tests/0003_agent_loop.py -v    # broker rank / decompose
pytest tests/0004_amm.py -v             # exchange curve
pytest tests/0005_ledger.py -v          # reputation settlement
pytest tests/0006_trading.py -v         # user trading
pytest tests/test_concurrency.py -v     # task cap, retries
pytest tests/test_sim_decision.py -v    # sim JSON parsing
```

## Branch status (concise)

| Branch | Feature |
|--------|---------|
| init / seed | Postgres schema, model IPO, agent registry |
| ledger / exchange | AMM, settlement, sequential subtask pipeline |
| investing | User trading, portfolio API |
| **simulation** (current) | Sim loops, external runner, concurrency caps |

See `docs/plans/backend-plan.md` for the full build plan.
