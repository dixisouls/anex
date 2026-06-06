# Agent Bazaar — Cloud Architecture (GCP)

> **Status:** design + spec. This document is the canonical cloud design for Agent Bazaar.
> It is consistent with `build_doc.md` (product/architecture spec) and
> `docs/plans/backend-plan.md` (branch-by-branch build plan). Where the three disagree,
> this file wins for *cloud topology and the ports/adapters seam*, `build_doc.md` wins for
> *product behaviour*, and the backend plan wins for *build order*.
>
> **Audience:** a solo developer who builds locally against Docker (Postgres + Redis) and
> deploys the same code to GCP for the demo. No frontend.
>
> **Last research pass:** 2026-06-06. Every version and product claim has a source in
> §13 (Library & Service Versions).

---

## 0. TL;DR / decisions locked

- **Local↔cloud parity via ports/adapters.** Application code (broker, ledger, exchange,
  API, sim) depends only on three interfaces — `Queue`, `EventBus`, `Embeddings` — never on
  a Cloud SDK directly. One env var, `RUNTIME_ENV` (`local` | `gcp`), selects the adapter set.
- **Hire dispatch = Google Cloud Tasks** in cloud (HTTP-push to the hired agent's Cloud Run
  URL, per-agent queue, built-in retries/backoff, OIDC service-to-service auth). Locally the
  same `Queue.enqueue_run(...)` call goes through an in-process HTTP adapter.
- **Event fan-out = Pub/Sub** in cloud (feeding the SSE `/feed` bridge); **Redis Stream**
  locally. Both behind the `EventBus` port. **Redis is present in BOTH environments**
  (Memorystore in cloud) for the hot path — vector index, leaderboard, live model prices,
  cache. Pub/Sub is *only* the cloud event transport, not a datastore.
- **Embeddings = GCP only.** The deterministic local-hash fallback is **removed**. Every
  embedding call goes to GCP via the Google Gen AI SDK (`google-genai`). Consequence:
  **local dev now requires GCP credentials** for embeddings. Tests inject a fake.
- **Datastores:** Cloud SQL for PostgreSQL (truth) + Memorystore for Redis 7.2+ (hot path).
  Local dev uses Docker Postgres 16 + Redis 8.
- **Compute:** Cloud Run services (api+broker; one per agent from a single parameterized
  image) + Cloud Run Jobs (migrate, seed). Scale-to-zero; `--min-instances=1` for the demo.
- **Memorystore vector module — RESOLVED (the headline risk).** Memorystore for Redis 7.2+
  supports vector search **natively in the engine** (FLAT + HNSW) via `FT.CREATE` /
  `FT.SEARCH`, which are **command-compatible with `redis-py` (dialect 2)**. It is **not**
  the third-party RediSearch module (Memorystore does **not** load third-party modules), but
  the subset we use (FLAT KNN over a HASH index) is supported. **No architecture change
  required.** See §9 for the detail, the supported-command subset, and the fallbacks.

---

## 1. Principles & the local↔cloud parity model

The product loop (broker hires an agent, judge scores it, ledger injects earnings into the
model stock, AMM reprices, investors trade) is **environment-agnostic**. Only three things
differ between a laptop and GCP:

| Concern | Local | Cloud (GCP) | Port |
|---|---|---|---|
| Dispatch a hire to an agent | in-process HTTP call (`httpx`) | Cloud Tasks HTTP push + OIDC | `Queue` |
| Fan out market events to `/feed` | Redis Stream `XADD`/`XREAD` | Pub/Sub topic + subscription (Redis Stream kept as replay log) | `EventBus` |
| Turn text into a vector | GCP `google-genai` | GCP `google-genai` (same) | `Embeddings` |
| Durable truth | Docker Postgres 16 | Cloud SQL for PostgreSQL | (SQLAlchemy URL only) |
| Hot path (vectors, leaderboard, prices, cache) | Docker Redis 8 | Memorystore for Redis 7.2+ | (Redis URL only) |

**The seam rule:** `backend/market/broker.py`, `backend/market/ledger.py`,
`backend/market/exchange.py`, `backend/api/*`, and `backend/sim/*` import the *port
interfaces* (`backend/ports/*`), obtained from a single factory
(`backend/ports/factory.py`) driven by `RUNTIME_ENV`. They never `import google.cloud.tasks`
or `from google.cloud import pubsub_v1`. Only the GCP adapter modules
(`backend/adapters/gcp_*.py`) touch the Cloud SDKs, and they import them lazily so local dev
does not need the SDKs at import time.

```
RUNTIME_ENV=local                         RUNTIME_ENV=gcp
┌─────────────────────────────┐           ┌─────────────────────────────┐
│ broker / ledger / api / sim │           │ broker / ledger / api / sim │   (identical code)
└──────────────┬──────────────┘           └──────────────┬──────────────┘
        ports.factory()                           ports.factory()
   ┌───────────┼───────────┐               ┌───────────────┼───────────────┐
   ▼           ▼           ▼               ▼               ▼               ▼
LocalQueue  LocalEventBus  GcpEmbeddings   GcpTasksQueue   GcpEventBus     GcpEmbeddings
(httpx)     (Redis Stream) (google-genai)  (Cloud Tasks)   (Pub/Sub+Redis) (google-genai)
```

Embeddings is GCP in *both* environments — there is no local embedding adapter for runtime
(only a `FakeEmbeddings` used in unit tests, never selected by `RUNTIME_ENV`).

---

## 2. Topology

```
                                  EXTERNAL DEPENDENCIES
                          ┌───────────────────────────────────┐
                          │  Weave / W&B (trace.wandb.ai)      │
                          │  OpenAI API (api.openai.com)       │
                          └───────────────────────────────────┘
                                     ▲             ▲
                                     │ traces      │ chat (worker variety + sim)
                                     │             │
   ┌──────────────────────────────────────────────────────────────────────────────────┐
   │ GCP project: agent-bazaar                                       region: us-central1 │
   │                                                                                    │
   │  ┌────────────────────────┐         enqueue (OIDC)      ┌──────────────────────┐  │
   │  │ Cloud Run: api-broker  │ ─────────────────────────►  │ Cloud Tasks          │  │
   │  │  (FastAPI: /task /feed │                             │  queue: agent-writer │  │
   │  │   /trade /models ...   │                             │  queue: agent-coder  │  │
   │  │   broker+ledger+AMM)   │ ◄───── result callback ──── │  queue: agent-...    │  │
   │  │  min-instances=1 (demo)│        (OIDC, /internal)    │  (one per agent)     │  │
   │  └───┬───────────┬────────┘                             └──────────┬───────────┘  │
   │      │           │  publish                                        │ HTTP push    │
   │      │           ▼                                                 ▼  (OIDC)       │
   │      │   ┌───────────────┐      push sub        ┌──────────────────────────────┐  │
   │      │   │ Pub/Sub       │ ───────────────────► │ Cloud Run: agent-<id>        │  │
   │      │   │ topic:        │ (or pull by api-     │  (one service per agent,      │  │
   │      │   │  market-feed  │  broker for SSE)     │   single parameterized image) │  │
   │      │   └───────────────┘                      │   POST /run  →  result cb     │  │
   │      │                                          └───────────────┬──────────────┘  │
   │      │ vectors / leaderboard / prices / cache                   │ model calls     │
   │      ▼ + Redis Stream replay log                                ▼                  │
   │  ┌───────────────────────┐                       ┌──────────────────────────────┐ │
   │  │ Memorystore for Redis  │                       │ Gemini Enterprise Agent       │ │
   │  │  7.2+ (private IP)     │                       │ Platform (google-genai)       │ │
   │  │  vector idx (FLAT KNN) │                       │  chat + embeddings            │ │
   │  └───────────────────────┘                       └──────────────────────────────┘ │
   │      ▲ Serverless VPC Access connector (10.8.0.0/28)                                │
   │      │                                                                              │
   │  ┌───┴────────────────────┐    Cloud SQL connector / Auth Proxy (private IP)        │
   │  │ Cloud SQL for          │ ◄───────────────────────────────────────────────────┐  │
   │  │ PostgreSQL 16          │                                                       │  │
   │  └────────────────────────┘                                                       │  │
   │      ▲                                                                            │  │
   │  ┌───┴───────────────┐    ┌──────────────────────┐    ┌────────────────────────┐ │  │
   │  │ Cloud Run Job:    │    │ Cloud Run Job:        │    │ Secret Manager         │ │  │
   │  │  migrate          │    │  seed                 │    │  DATABASE_URL, REDIS_   │ │  │
   │  │ (alembic upgrade) │    │ (seed both markets)   │    │  URL, OPENAI_API_KEY,   │─┘  │
   │  └───────────────────┘    └──────────────────────┘    │  WANDB_API_KEY, ...     │    │
   │                                                        └────────────────────────┘    │
   │  ┌──────────────────────────────────────────────────────────────────────────────┐  │
   │  │ Artifact Registry: agent-bazaar/api , agent-bazaar/agent (single agent image)  │  │
   │  └──────────────────────────────────────────────────────────────────────────────┘  │
   └──────────────────────────────────────────────────────────────────────────────────┘
```

**Component inventory**

| GCP resource | Name (suggested) | Purpose |
|---|---|---|
| Cloud Run service | `api-broker` | FastAPI app: API routes, broker, ledger, exchange, sim; enqueues hires; bridges events to SSE `/feed` |
| Cloud Run service | `agent-<id>` (e.g. `agent-writer-01`) | One per seed agent, single parameterized image, `POST /run` |
| Cloud Run Job | `migrate` | `alembic upgrade head` |
| Cloud Run Job | `seed` | seed both markets (models, agents, sim users) |
| Cloud Tasks queue | `agent-<id>` (one per agent) | per-agent dispatch queue with retries/backoff |
| Cloud Tasks queue | `run-results` (optional) | durable result callbacks to the API |
| Pub/Sub topic | `market-feed` | every market event (see `build_doc` §3.1) |
| Pub/Sub subscription | `market-feed-sse` | feeds the API's SSE bridge (pull) |
| Cloud SQL | `bazaar-pg` (PostgreSQL 16) | durable source of truth |
| Memorystore for Redis | `bazaar-redis` (7.2+) | hot path: vector index, leaderboard, live prices, cache, Stream replay |
| Serverless VPC Access | `bazaar-vpc` (`10.8.0.0/28`) | Cloud Run → Memorystore/Cloud SQL private IP |
| Secret Manager | several secrets | all connection strings + API keys |
| Artifact Registry | `agent-bazaar` (Docker) | `api` and `agent` images |

---

## 3. The ports/adapters seam (interfaces)

New package layout (added by the `feat/cloud-infra` branch; see backend plan):

```
backend/ports/
  __init__.py
  queue.py        # Queue protocol + RunDispatch dataclass
  event_bus.py    # EventBus protocol
  embeddings.py   # Embeddings protocol
  factory.py      # get_queue(), get_event_bus(), get_embeddings() switched by RUNTIME_ENV
backend/adapters/
  local_queue.py      # httpx in-process dispatch
  local_event_bus.py  # Redis Stream (wraps existing feed.emit/read_new)
  gcp_queue.py        # Cloud Tasks
  gcp_event_bus.py    # Pub/Sub publish + Redis Stream replay; pull bridge for SSE
  gcp_embeddings.py   # google-genai embed_content
  fake_embeddings.py  # tests only
```

### 3.1 `Queue` — hire dispatch

```python
# backend/ports/queue.py
from dataclasses import dataclass, field
from typing import Protocol

@dataclass
class RunDispatch:
    subtask_id: str             # idempotency / dedup key
    agent_id: str
    service_url: str            # agent base URL (localhost in dev, Cloud Run URL in cloud)
    subtask_text: str
    config: dict                # {"model","provider","system","tools"}
    task_id: str

class Queue(Protocol):
    async def enqueue_run(self, dispatch: RunDispatch) -> str:
        """Dispatch a single hire to an agent's POST /run. Returns a dispatch id.
        Fire-and-continue: the run RESULT comes back via the result-callback path
        (handle_run_result), NOT as the return value, so local and cloud behave the same."""
        ...
```

- **`LocalQueue`** (`RUNTIME_ENV=local`): `await httpx.post(f"{service_url}/run", json=...)`,
  read `{"output": ...}` from the response, then call the shared
  `broker.handle_run_result(subtask_id, agent_id, output)` directly (which judges + settles +
  emits). Spawned as an `asyncio.create_task` with its own session/Redis scope so `/task`
  returns immediately. Returns a synthetic dispatch id.
- **`GcpTasksQueue`** (`RUNTIME_ENV=gcp`): creates a Cloud Task on the agent's queue with an
  OIDC token (audience = agent service URL). Cloud Tasks pushes to the agent `/run`. Because
  **Cloud Tasks ignores the HTTP response body** (it only uses the status code for
  retry/ack), the agent must send its output back via the **result callback** (§4). The
  task **name** is set to a dedup key derived from `subtask_id` so a duplicated enqueue
  within the dedup window is dropped by Cloud Tasks.

Both adapters consume the same `RunDispatch`. The broker is identical:

```python
# inside broker.run_task(...), per subtask
await queue.enqueue_run(RunDispatch(
    subtask_id=st.subtask_id, agent_id=top.agent_id, service_url=a.service_url,
    subtask_text=st.text, config=config, task_id=task_id,
))
# broker does NOT await the model output here; judging/settling happens in handle_run_result
```

### 3.2 `EventBus` — market events

```python
# backend/ports/event_bus.py
from typing import AsyncIterator, Protocol
from contracts.events import MarketEvent

class EventBus(Protocol):
    async def publish(self, event: MarketEvent) -> None:
        """Emit one market event to all consumers."""
        ...

    def subscribe(self, *, from_id: str = "$") -> AsyncIterator[tuple[str, MarketEvent]]:
        """Async-iterate (cursor, event) pairs for the SSE /feed loop.
        from_id: '$' = only new events; '0' = from the beginning (replay)."""
        ...
```

- **`LocalEventBus`** (`RUNTIME_ENV=local`): thin wrapper over the existing
  `backend/market/feed.py` — `publish` = `XADD market:feed`, `subscribe` = `XREAD` loop.
  The Redis Stream is the durable replay log; `from_id="0"` replays.
- **`GcpEventBus`** (`RUNTIME_ENV=gcp`): `publish` does **both** (a) Pub/Sub `publish` to
  topic `market-feed` for live fan-out and (b) `XADD market:feed` to Memorystore as the
  durable replay/audit log (dual-write — see Open Question Q1). `subscribe` runs a streaming
  pull on subscription `market-feed-sse` and yields decoded events to the SSE loop. For
  `from_id="0"` replay it reads the Redis Stream (Pub/Sub is not a replayable log).

Every module that emits events calls `event_bus.publish(event)` instead of `feed.emit(r, event)`.
(`feed.emit` stays as the implementation detail inside `LocalEventBus` / the Redis replay write.)

### 3.3 `Embeddings` — text → vector (GCP only)

```python
# backend/ports/embeddings.py
from typing import Protocol
import numpy as np

class Embeddings(Protocol):
    def embed(self, text: str) -> np.ndarray:        # float32, L2-normalized, len == VECTOR_DIM
        ...
    def embed_bytes(self, text: str) -> bytes:       # little-endian float32 bytes for Redis
        ...
```

- **`GcpEmbeddings`** (the only runtime adapter): `google-genai` `embed_content` with
  `model=GCP_EMBED_MODEL` (`gemini-embedding-001`), `config=EmbedContentConfig(
  output_dimensionality=VECTOR_DIM, task_type=...)`, then **manual L2 normalization** (see
  §8 — `gemini-embedding-001` does not auto-normalize truncated dims). Raises if the returned
  dimension ≠ `VECTOR_DIM` so a model/dim mismatch fails loudly.
- **`FakeEmbeddings`** (tests only): deterministic hash vector, dim = `VECTOR_DIM`. Selected
  only when `EMBEDDINGS_FAKE=1` in unit tests; **never** via `RUNTIME_ENV`. This replaces the
  old `EMBED_BACKEND=local` production path, which is deleted.

### 3.4 Factory + env flag

```python
# backend/ports/factory.py
from functools import cache
from backend.config import RUNTIME_ENV

@cache
def get_queue():
    if RUNTIME_ENV == "gcp":
        from backend.adapters.gcp_queue import GcpTasksQueue
        return GcpTasksQueue()
    from backend.adapters.local_queue import LocalQueue
    return LocalQueue()

@cache
def get_event_bus():
    if RUNTIME_ENV == "gcp":
        from backend.adapters.gcp_event_bus import GcpEventBus
        return GcpEventBus()
    from backend.adapters.local_event_bus import LocalEventBus
    return LocalEventBus()

@cache
def get_embeddings():
    import os
    if os.getenv("EMBEDDINGS_FAKE") == "1":
        from backend.adapters.fake_embeddings import FakeEmbeddings
        return FakeEmbeddings()
    from backend.adapters.gcp_embeddings import GcpEmbeddings
    return GcpEmbeddings()
```

`RUNTIME_ENV` defaults to `local`. Cloud Run services set `RUNTIME_ENV=gcp`.

---

## 4. Hire dispatch flow (Cloud Tasks)

```
/task ──► broker.decompose ──► per subtask: rank ──► queue.enqueue_run(RunDispatch)
                                                            │
                          RUNTIME_ENV=local                 │   RUNTIME_ENV=gcp
              ┌─────────────────────────────────┐          │   ┌──────────────────────────────────┐
              │ LocalQueue: httpx POST /run      │          │   │ GcpTasksQueue: create_task        │
              │  → output → handle_run_result()  │          │   │  (queue agent-<id>, OIDC token,   │
              └─────────────────────────────────┘          │   │   name=dedup(subtask_id))         │
                                                            │   └──────────────┬───────────────────┘
                                                            │        Cloud Tasks HTTP push (OIDC)
                                                            │                  ▼
                                                            │   ┌──────────────────────────────────┐
                                                            │   │ agent-<id> Cloud Run: POST /run    │
                                                            │   │  execute(model) → output           │
                                                            │   │  POST API /internal/runs/result    │
                                                            │   │   (OIDC, body {subtask_id, agent,  │
                                                            │   │    output}) → 200                  │
                                                            │   └──────────────┬───────────────────┘
                                                            ▼                  ▼
                                          api-broker: handle_run_result(subtask_id, agent_id, output)
                                            → judge → ledger.settle → exchange.inject_earnings
                                            → event_bus.publish(task_executed/task_scored/...)
```

**Enqueue (cloud)** — `gcp_queue.py` (uses `google-cloud-tasks` 2.22.0):

```python
from google.cloud import tasks_v2

def _enqueue(self, d: RunDispatch) -> str:
    client = tasks_v2.CloudTasksClient()
    parent = client.queue_path(PROJECT, LOCATION, f"agent-{d.agent_id}")
    task = tasks_v2.Task(
        name=f"{parent}/tasks/{_dedup(d.subtask_id)}",          # dedup within ~1h window
        http_request=tasks_v2.HttpRequest(
            http_method=tasks_v2.HttpMethod.POST,
            url=f"{d.service_url}/run",
            headers={"Content-Type": "application/json"},
            body=json.dumps({"subtask_id": d.subtask_id, "task_id": d.task_id,
                             "agent_id": d.agent_id, "subtask_text": d.subtask_text,
                             "config": d.config, "result_url": f"{API_URL}/internal/runs/result"}).encode(),
            oidc_token=tasks_v2.OidcToken(
                service_account_email=TASKS_INVOKER_SA,           # has roles/run.invoker on agents
                audience=d.service_url),                          # = agent base URL
        ),
    )
    return client.create_task(parent=parent, task=task).name
```

**Retries / backoff:** configured on the queue, not in code — e.g.
`gcloud tasks queues update agent-writer-01 --max-attempts=5 --min-backoff=2s --max-backoff=30s --max-doublings=4`.
Cloud Tasks retries any non-2xx from the agent automatically.

**Idempotency / dedup:**
1. **Enqueue dedup** — task `name = dedup(subtask_id)`; Cloud Tasks rejects a duplicate name
   for ~1 hour after the original was created/completed.
2. **Result idempotency** — `handle_run_result` checks whether `subtask_id` already has a
   `judge_score` persisted; if so it no-ops. This makes a retried push (which produced a
   second result) safe.

**Agent `/run` handler (cloud mode):** execute the model, then POST the result to
`result_url` with its own OIDC token (audience = `API_URL`), return `200` quickly so Cloud
Tasks acks. In local mode the agent simply returns `{"output": ...}` and `LocalQueue` reads
it directly — the agent code is identical; only who consumes the output differs, gated by
whether `result_url` is present in the request body.

**Local adapter equivalent:** `LocalQueue.enqueue_run` does the HTTP call in-process and
invokes `handle_run_result` itself. Same broker code, same result handler, no Cloud SDK.

---

## 5. Event distribution flow (Pub/Sub) + the SSE bridge

```
producers (broker, ledger, exchange, trade, sim)
        │  event_bus.publish(event)
        ▼
 RUNTIME_ENV=local                         RUNTIME_ENV=gcp
 ┌───────────────────────┐                 ┌───────────────────────────────────────────┐
 │ XADD market:feed      │                 │ (a) Pub/Sub publish → topic market-feed     │
 │ (Redis Stream)        │                 │ (b) XADD market:feed (Memorystore replay)   │
 └──────────┬────────────┘                 └───────────────┬─────────────────────────────┘
            │ XREAD                                          │ streaming pull (market-feed-sse)
            ▼                                                ▼
   GET /feed (SSE)  ◄──────── EventSourceResponse ◄────── in-process broadcaster
   text/event-stream                                    (fans one subscription to N clients)
```

**Why Redis stays in cloud:** Pub/Sub is the *fan-out transport* only. The hot path —
capability vector KNN, the leaderboard zset, `model:{id}` live prices, derived-price reads —
lives in Memorystore in both environments. Pub/Sub never stores app state.

**SSE bridge (cloud):** the API holds one streaming-pull subscriber on `market-feed-sse` and
an in-process broadcaster (a set of `asyncio.Queue`s, one per connected `/feed` client). Each
pulled message is decoded to a `MarketEvent` and pushed to every client queue; messages are
acked after broadcast.

> **Multi-instance caveat (important for SSE).** With a single shared subscription, Pub/Sub
> load-balances messages across subscriber instances, so a client connected to instance A
> would miss events delivered to instance B. For the demo, run `api-broker` with
> `--min-instances=1 --max-instances=1` (one instance, one subscription) — simplest and
> sufficient. To scale `/feed` horizontally later, give **each instance its own
> subscription** (create-on-startup, delete-on-shutdown) so every instance receives every
> event. This is documented as Open Question Q2.

**Replay / `/seed` clean reset:** the Redis Stream remains the replay log in both
environments (`subscribe(from_id="0")`). Pub/Sub is not used for replay.

**Push vs pull:** we use a **pull** subscription consumed by the API (keeps the SSE bridge in
one process, no extra public endpoint, no Pub/Sub→Cloud Run auth dance). A push subscription
to `/internal/pubsub/push` is a viable alternative if you prefer Pub/Sub to drive delivery;
it needs an OIDC-authenticated push endpoint and still needs the in-process broadcaster for
SSE fan-out. Pull is recommended for this solo build.

---

## 6. Data layer (Cloud SQL + Memorystore)

### 6.1 Cloud SQL for PostgreSQL (truth)

- **Instance:** `bazaar-pg`, PostgreSQL 16, **private IP** (no public IP for the demo path).
- **Connectivity from Cloud Run — two supported options:**
  1. **Cloud SQL Python Connector** (`cloud-sql-python-connector[asyncpg]` 1.20.3) with
     `create_async_connector(refresh_strategy="lazy")` and `ip_type=IPTypes.PRIVATE`. The
     `lazy` refresh strategy is recommended for Cloud Run (CPU is throttled outside a
     request). SQLAlchemy async engine uses an `async_creator` that calls the connector.
  2. **Cloud SQL Auth Proxy / `--set-cloudsql-instances`** on the Cloud Run service/job
     (Unix socket at `/cloudsql/PROJECT:REGION:INSTANCE`), with the plain `asyncpg` driver.
  We recommend **option 1** (the Python Connector) because it gives IAM-based auth and works
  identically for services and jobs; it requires private IP reachability, hence the VPC
  connector. Either way, **the application only ever sees `DATABASE_URL`** — the connector
  wiring lives in `backend/infra/db.py` behind `RUNTIME_ENV`, not in app code.
- **Private IP requires VPC access:** the Cloud Run service attaches the
  **Serverless VPC Access** connector (`bazaar-vpc`) so it can reach the instance's private IP.
- **Migrations:** run as a **Cloud Run Job** (`migrate` → `alembic upgrade head`) with the
  same image, `--set-secrets DATABASE_URL=...`, the VPC connector, and the Cloud SQL instance
  attached. Jobs run to completion and exit (no min-instances concept).

### 6.2 Memorystore for Redis (hot path)

- **Instance:** `bazaar-redis`, Redis **7.2 or newer** (vector search requires ≥ 7.2),
  private IP, in the same region/VPC.
- **Reached via the same Serverless VPC Access connector** (`bazaar-vpc`). Memorystore has no
  public IP; Cloud Run *must* use the VPC connector to reach it.
- **App sees only `REDIS_URL`** (e.g. `redis://10.x.x.x:6379`). `backend/infra/redis_client.py`
  is unchanged.
- **Vector index:** FLAT KNN over the `agents_idx` HASH index — exactly what
  `backend/market/registry.py` already creates. See §9 for the compatibility analysis.

### 6.3 Local docker-compose equivalent

Unchanged from today: `docker compose up -d postgres redis` (Postgres 16, Redis 8), `alembic
upgrade head`, `python -m backend.market.seeder`. `DATABASE_URL` and `REDIS_URL` point at
localhost. `RUNTIME_ENV=local`. The only new local requirement is **GCP credentials for
embeddings** (`GOOGLE_APPLICATION_CREDENTIALS` or ADC, plus `GCP_PROJECT`/`GCP_LOCATION`).

---

## 7. Security / IAM

**Per-service service accounts (least privilege):**

| Service account | Attached to | Roles |
|---|---|---|
| `sa-api-broker` | `api-broker` Cloud Run | `roles/cloudtasks.enqueuer`, `roles/iam.serviceAccountUser` (to mint OIDC for tasks), `roles/pubsub.publisher` + `roles/pubsub.subscriber` (topic/sub), `roles/cloudsql.client`, `roles/secretmanager.secretAccessor`, `roles/aiplatform.user` (Gemini Enterprise Agent Platform), `roles/run.invoker` on each `agent-<id>` (for the result-callback path is reversed — see below) |
| `sa-agent` | every `agent-<id>` Cloud Run | `roles/secretmanager.secretAccessor`, `roles/aiplatform.user`, `roles/run.invoker` on `api-broker` (to POST the result callback), `roles/cloudsql.client` if the agent ever needs the DB (it should not — agents are stateless) |
| `sa-tasks-invoker` | used as the OIDC identity in Cloud Tasks `oidc_token` | `roles/run.invoker` on each `agent-<id>`; `sa-api-broker` must be able to `actAs` it (or reuse `sa-api-broker` itself as the invoker SA, granting it `run.invoker` on agents) |
| `sa-jobs` | `migrate`, `seed` Cloud Run Jobs | `roles/cloudsql.client`, `roles/secretmanager.secretAccessor`, `roles/aiplatform.user` (seed embeds capability text) |

**OIDC service-to-service auth:**
- Cloud Tasks → agent: task carries an OIDC token (`audience` = agent URL); the agent service
  is deployed **without** `--allow-unauthenticated`; only callers with `run.invoker` (the
  invoker SA) can reach it.
- agent → api-broker result callback: the agent mints an OIDC token (audience = `API_URL`)
  using its own SA; `api-broker`'s `/internal/*` routes require authentication
  (`run.invoker`). The public routes (`/task`, `/feed`, `/models`, `/trade`, …) are
  `--allow-unauthenticated` for the demo (add API-key/IAP later).

**Secrets (Secret Manager, accessed by `secretAccessor`):**

| Secret | Consumed by | Notes |
|---|---|---|
| `DATABASE_URL` | api-broker, jobs | Cloud SQL connection (or connector instance name) |
| `REDIS_URL` | api-broker, jobs | Memorystore private IP URL |
| `OPENAI_API_KEY` | api-broker, agents | worker variety + simulation |
| `WANDB_API_KEY` | api-broker, agents | Weave tracing (mandatory) |
| `GCP creds` | — | not a secret; uses the attached SA / ADC. Only set `GCP_PROJECT`/`GCP_LOCATION` as env |

Mount secrets as **env vars pinned to a version** (resolved at instance startup), or as files
for rotation (Cloud Run re-reads file-mounted secrets at runtime). Do **not** use `:latest`
for env-var secrets in production-ish setups.

---

## 8. Embeddings (GCP-only) — model, dimension, normalization

**Decision:** remove the local-hash fallback; always call GCP. Model: **`gemini-embedding-001`**
(GA text embedding model) via `google-genai`. Reconciliation with the old plan: the backend
plan's "keep a local fallback" tasks and the `EMBED_BACKEND=local`/`vertex` config are
**retired**; see the updated backend plan Branch 0/1.

```python
# backend/adapters/gcp_embeddings.py  (lazy import keeps non-GCP imports clean)
from google import genai
from google.genai import types
import numpy as np
from backend.config import GCP_PROJECT, GCP_LOCATION, GCP_EMBED_MODEL, VECTOR_DIM

class GcpEmbeddings:
    def __init__(self):
        self._client = genai.Client(vertexai=True, project=GCP_PROJECT, location=GCP_LOCATION)

    def embed(self, text: str) -> np.ndarray:
        resp = self._client.models.embed_content(
            model=GCP_EMBED_MODEL,                              # "gemini-embedding-001"
            contents=text,
            config=types.EmbedContentConfig(
                output_dimensionality=VECTOR_DIM,              # 768
                task_type="RETRIEVAL_DOCUMENT",                # query side uses RETRIEVAL_QUERY
            ),
        )
        arr = np.asarray(resp.embeddings[0].values, dtype=np.float32)
        if arr.shape[0] != VECTOR_DIM:
            raise ValueError(f"{GCP_EMBED_MODEL} returned dim {arr.shape[0]} != VECTOR_DIM {VECTOR_DIM}")
        n = float(np.linalg.norm(arr))                          # MANUAL L2 normalization
        return arr / n if n > 0 else arr                        # required for <3072 dims on gemini-embedding-001

    def embed_bytes(self, text: str) -> bytes:
        return self.embed(text).tobytes()
```

**Critical embedding facts (verified 2026-06-06):**
- `gemini-embedding-001` default dimension is **3072**; recommended truncations are
  **768 / 1536 / 3072** via `output_dimensionality`. We use **768** to keep `VECTOR_DIM=768`
  and the existing `agents_idx` schema unchanged.
- At any non-3072 dimension, `gemini-embedding-001` **does not auto-normalize** — you must L2
  normalize yourself for correct cosine similarity. (Its successor `gemini-embedding-2` does
  auto-normalize truncated dims, but it is multimodal and overkill for text capability
  matching; flagged as an option in Q4.)
- `text-embedding-004` was **deprecated 2026-01-14**; `text-embedding-005` is older than
  `gemini-embedding-001`. Use `gemini-embedding-001`.
- **DIM must match the index.** If you change the embedding model or `output_dimensionality`,
  you must change `VECTOR_DIM` and rebuild `agents_idx`. The adapter raises on mismatch.
- **Query vs document task_type matters** for retrieval quality: embed capability text with
  `RETRIEVAL_DOCUMENT`, embed subtask queries with `RETRIEVAL_QUERY`.

**Consequence (flagged loudly):** local dev now needs GCP credentials and network for any
path that embeds (seeding, hiring). Offline unit tests set `EMBEDDINGS_FAKE=1` to use
`FakeEmbeddings`. There is no offline production embedding path anymore.

---

## 9. Memorystore vector module — the headline risk, resolved

**Question:** does Memorystore for Redis support the vector search we rely on (`agents_idx`
FLAT KNN created via `redis-py`'s `FT.CREATE` / queried via `FT.SEARCH` with dialect 2)?

**Answer: YES — natively, not via a module.**

- Memorystore for Redis **7.2+** ships **vector search built into the engine** (first-class
  vector data type), supporting both **FLAT** (exact KNN) and **HNSW** (approximate). Source:
  Google Cloud Memorystore "Vector search" + "Supported versions" docs (§13).
- It exposes the standard `FT.*` surface for vectors: `FT.CREATE`, `FT.SEARCH`, `FT.INFO`,
  `FT._LIST`, `FT.DROPINDEX`, `INFO`. These are **command-compatible with `redis-py`** using
  **`DIALECT 2`** — exactly what `backend/market/registry.py` already does
  (`VectorField(..., "FLAT", {...COSINE...})`, `Query("*=>[KNN k @embedding $vec AS score]").dialect(2)`).
- It is **not** the third-party RediSearch module. **Memorystore does not load third-party
  Redis modules.** But the subset we use (vector index over a HASH, KNN search) does not need
  the module — it needs the native vector feature, which is present.

**Implications / required care:**
1. **Keep FLAT** for `agents_idx` (we already do). FLAT gives exact KNN — correct for a small
   roster (6–8 agents → tens, not millions, of vectors). HNSW is available if the roster ever
   grows large.
2. **Supported-command subset only.** Memorystore's native vector search supports the `FT.*`
   commands listed above; full RediSearch extras (e.g. `FT.AGGREGATE`, standalone full-text)
   are **not** guaranteed. We use none of those — only `FT.CREATE`/`FT.SEARCH`/`FT.DROPINDEX`.
   If a future `redis-py` helper emits an unsupported arg, fall back to
   `r.execute_command("FT.SEARCH", ...)` (the raw form Memorystore documents).
3. **Tag/numeric fields only work alongside a vector** on Memorystore (hybrid queries). We do
   not index tags/numerics, so this is a non-issue.
4. **Index type = HASH** with a key prefix (`agent:`) — matches our projection exactly.

**Fallbacks (only if a constraint surfaces during deploy — none expected):**
- **Redis Cloud / Redis Enterprise on GCP Marketplace** — full RediSearch module, vector +
  JSON + full-text. Use if you later need module-only features. App change = `REDIS_URL` only.
- **Self-hosted Redis 8 on Cloud Run/GCE** — Redis 8 ships the query engine + vector search
  in core (this is what local dev uses). Run a single small VM/Cloud Run sidecar. More ops.
- Both are drop-in at the `REDIS_URL` level; no application code changes thanks to the hot
  path being plain `redis-py` commands.

**Bottom line:** the locked architecture (Memorystore for the hot path incl. vector KNN)
**stands**. Recommendation: **Memorystore for Redis 7.2+ (single node, Basic tier is fine for
the demo), FLAT index.**

---

## 10. Deployment

### 10.1 Artifact Registry + images

Two images, one repo:
- `agent-bazaar/api` — the FastAPI app (broker, ledger, exchange, sim, SSE bridge).
- `agent-bazaar/agent` — the **single parameterized agent image**; one Cloud Run service per
  agent from this one image, differing only by env (`AGENT_ID`, `AGENT_SYSTEM_PROMPT`, port).

In practice both can be the **same** image (the repo's `Dockerfile`) with different
entrypoints/commands; keeping two logical names documents intent. Build with Cloud Build or
`gcloud run deploy --source` (Buildpacks) or `gcloud builds submit` + a Dockerfile.

```bash
# Build & push (Dockerfile route)
gcloud artifacts repositories create agent-bazaar --repository-format=docker --location=us-central1
gcloud builds submit --tag us-central1-docker.pkg.dev/$PROJECT/agent-bazaar/api:$(git rev-parse --short HEAD)
```

### 10.2 Concrete gcloud (representative — see Q3 on Terraform vs scripts)

```bash
PROJECT=agent-bazaar; REGION=us-central1
IMG=us-central1-docker.pkg.dev/$PROJECT/agent-bazaar/api:latest

# --- VPC connector (Cloud Run → private Memorystore/Cloud SQL) ---
gcloud compute networks vpc-access connectors create bazaar-vpc --region=$REGION --range=10.8.0.0/28

# --- Cloud SQL (private IP) + Memorystore (7.2+) ---
gcloud sql instances create bazaar-pg --database-version=POSTGRES_16 --region=$REGION \
  --no-assign-ip --network=default --tier=db-custom-1-3840
gcloud redis instances create bazaar-redis --region=$REGION --redis-version=redis_7_2 \
  --size=1 --connect-mode=PRIVATE_SERVICE_ACCESS --network=default

# --- Secrets ---
printf '%s' "$DB_URL"  | gcloud secrets create DATABASE_URL --data-file=-
printf '%s' "$RDS_URL" | gcloud secrets create REDIS_URL --data-file=-
printf '%s' "$OPENAI"  | gcloud secrets create OPENAI_API_KEY --data-file=-
printf '%s' "$WANDB"   | gcloud secrets create WANDB_API_KEY --data-file=-

# --- Migrate + seed as Cloud Run Jobs ---
gcloud run jobs create migrate --image $IMG --region $REGION --service-account sa-jobs@$PROJECT.iam.gserviceaccount.com \
  --vpc-connector bazaar-vpc --set-secrets DATABASE_URL=DATABASE_URL:latest \
  --set-env-vars RUNTIME_ENV=gcp,GCP_PROJECT=$PROJECT,GCP_LOCATION=$REGION \
  --command alembic --args upgrade,head
gcloud run jobs execute migrate --region $REGION --wait
gcloud run jobs create seed --image $IMG --region $REGION --service-account sa-jobs@$PROJECT.iam.gserviceaccount.com \
  --vpc-connector bazaar-vpc \
  --set-secrets DATABASE_URL=DATABASE_URL:latest,REDIS_URL=REDIS_URL:latest,WANDB_API_KEY=WANDB_API_KEY:latest \
  --set-env-vars RUNTIME_ENV=gcp,GCP_PROJECT=$PROJECT,GCP_LOCATION=$REGION \
  --command python --args -m,backend.market.seeder
gcloud run jobs execute seed --region $REGION --wait

# --- Per-agent Cloud Tasks queues (one per agent) ---
for A in writer-01 coder-01 summarizer-01 factcheck-01 translator-01 planner-01; do
  gcloud tasks queues create agent-$A --location=$REGION \
    --max-attempts=5 --min-backoff=2s --max-backoff=30s
done

# --- Pub/Sub topic + pull subscription for the SSE bridge ---
gcloud pubsub topics create market-feed
gcloud pubsub subscriptions create market-feed-sse --topic=market-feed --ack-deadline=30

# --- Agent services (one per agent, single image, authenticated) ---
gcloud run deploy agent-writer-01 --image $IMG --region $REGION --no-allow-unauthenticated \
  --service-account sa-agent@$PROJECT.iam.gserviceaccount.com --vpc-connector bazaar-vpc \
  --set-secrets OPENAI_API_KEY=OPENAI_API_KEY:latest,WANDB_API_KEY=WANDB_API_KEY:latest \
  --set-env-vars RUNTIME_ENV=gcp,GCP_PROJECT=$PROJECT,GCP_LOCATION=$REGION,AGENT_ID=writer-01 \
  --command python --args -m,backend.agent.main --min-instances=1   # warm for the demo

# --- API + broker service (public; one instance for SSE simplicity) ---
gcloud run deploy api-broker --image $IMG --region $REGION --allow-unauthenticated \
  --service-account sa-api-broker@$PROJECT.iam.gserviceaccount.com --vpc-connector bazaar-vpc \
  --set-secrets DATABASE_URL=DATABASE_URL:latest,REDIS_URL=REDIS_URL:latest,OPENAI_API_KEY=OPENAI_API_KEY:latest,WANDB_API_KEY=WANDB_API_KEY:latest \
  --set-env-vars RUNTIME_ENV=gcp,GCP_PROJECT=$PROJECT,GCP_LOCATION=$REGION,API_URL=https://api-broker-...run.app \
  --min-instances=1 --max-instances=1
```

After deploy, repoint each agent's `service_url` (in Postgres/registry) from `localhost:900x`
to its Cloud Run URL (a seed/config step). The broker only knows the URL, so nothing in the
broker changes — exactly the `build_doc` §8 cutover promise, now expressed through the `Queue`
port.

### 10.3 env/config strategy

- `RUNTIME_ENV` (`local`|`gcp`) — the one seam flag.
- `GCP_PROJECT`, `GCP_LOCATION`, `GCP_CHAT_MODEL`, `GCP_EMBED_MODEL`.
- `OPENAI_API_KEY`, `OPENAI_CHAT_MODEL`.
- `DATABASE_URL`, `REDIS_URL` (secrets).
- `WEAVE_PROJECT`, `WANDB_API_KEY`, `WEAVE_DISABLED`.
- `API_URL` (for the result-callback audience), per-agent `AGENT_ID`.
- Cloud-only: `TASKS_INVOKER_SA`, Pub/Sub topic/sub names (defaulted).

---

## 11. Observability

- **Weave (mandatory).** `weave.init(WEAVE_PROJECT)` once per process — in the API lifespan
  and in each agent `main`. `@weave.op` on every LLM call (broker decompose, rank, agent
  execute, judge, sim decisions) and every exchange op (buy/sell/inject). `WANDB_API_KEY`
  comes from Secret Manager; `WEAVE_DISABLED=1` for offline tests. Weave runs identically in
  local and cloud (it is an external SaaS dependency, not a GCP product).
- **Cloud Logging / Cloud Trace.** Cloud Run captures stdout/stderr to Cloud Logging
  automatically; structured JSON logs recommended. Optionally enable Cloud Trace for
  request-level latency across `api-broker` ↔ Cloud Tasks ↔ agents (OpenTelemetry; `redis-py`
  exposes basic OTel classes). Weave remains the primary tool for the demo curves
  (success rate, cost/task, price history, portfolio returns).

---

## 12. Cost & scale

- **Scale-to-zero** on all Cloud Run services by default (no traffic = no cost). Cloud SQL and
  Memorystore are the standing-cost items; pick the smallest tiers for a hackathon
  (`db-custom-1-3840`, Memorystore `--size=1`).
- **Cold starts:** per-agent services and `api-broker` will cold-start from zero. For the live
  demo set `--min-instances=1` on the demo agents and `api-broker` to keep them warm; revert
  to `0` after. (Cloud Run **Jobs** have no min-instances — they run to completion.)
- **Cloud Tasks / Pub/Sub** are pay-per-use and trivially cheap at demo volume.
- **Embeddings** now hit GCP for every seed/hire embed — small text, `gemini-embedding-001`
  is ~\$0.15 / 1M tokens; negligible at demo scale but no longer free/offline.

---

## 13. Library & Service Versions (latest as of 2026-06-06)

All versions verified via web search on 2026-06-06. Pin these in `requirements.txt`.

| Library / product | Pinned / target | Latest (date) | Source |
|---|---|---|---|
| `google-genai` (Gen AI SDK) | `>=2.8,<3` | 2.8.0 (2026-06-03) | github.com/googleapis/python-genai (releases) |
| `openai` | `>=2.41,<3` | 2.41.0 (2026-06-03) | pypi.org/project/openai |
| `weave` | `>=0.52.42` | 0.52.42 (2026-06-02) | pypi.org/project/weave |
| `fastapi` | `>=0.136.3` | 0.136.3 (2026-05-23) | pypi.org/project/fastapi |
| `uvicorn[standard]` | `>=0.49` | 0.49.0 (2026-06-03) | pypi.org/project/uvicorn |
| `sse-starlette` | `>=3.4.4` | 3.4.4 (2026-05-12) | pypi.org/project/sse-starlette |
| `httpx` | `>=0.28.1,<1` | 0.28.1 (2024-12-06) | pypi.org/project/httpx |
| `sqlalchemy[asyncio]` | `>=2.0.50,<2.1` | 2.0.50 (2026-05-24) | pypi.org/project/SQLAlchemy |
| `asyncpg` | `>=0.31` | 0.31.0 (2025-11-24) | pypi.org/project/asyncpg |
| `alembic` | `>=1.18.4` | 1.18.4 (2026-02-10) | pypi.org/project/alembic |
| `redis` (redis-py) | `>=8.0,<9` | 8.0.0 (2026-05-28) | pypi.org/project/redis |
| `pydantic` | `>=2.13.4,<3` | 2.13.4 (2026-05-06) | pypi.org/project/pydantic |
| `numpy` | `>=2.4.6,<2.5` | 2.4.6 (2026-05-18) | pypi.org/project/numpy |
| `google-cloud-tasks` | `>=2.22` | 2.22.0 (2026-03-26) | pypi.org/project/google-cloud-tasks |
| `google-cloud-pubsub` | `>=2.38` | 2.38.0 (2026-05-07) | pypi.org/project/google-cloud-pubsub |
| `google-cloud-secret-manager` | `>=2.28` | 2.28.0 (2026-05-07) | pypi.org/project/google-cloud-secret-manager |
| `cloud-sql-python-connector[asyncpg]` | `>=1.20.3` | 1.20.3 (2026-05-27) | pypi.org/project/cloud-sql-python-connector |
| `pytest` | `>=8.4` | 8.4.x | required by pytest-asyncio 1.4.0 |
| `pytest-asyncio` | `>=1.4` | 1.4.0 (2026-05-26) | pypi.org/project/pytest-asyncio |

**GCP product facts (verified 2026-06-06):**

| Product | Fact | Source |
|---|---|---|
| Gemini Enterprise Agent Platform | Renamed from Vertex AI (Google Cloud Next '26). All Vertex AI roadmap delivered through Agent Platform. Accessed via `google-genai` (`vertexai=True`). | cloud.google.com/blog "Introducing Gemini Enterprise Agent Platform"; docs vertex-ai-name-changes |
| Gemini chat model ids | `gemini-3.5-flash` (stable, 2026-05-19), `gemini-3.1-pro-preview` (preview), `gemini-3.1-flash-lite` (stable, 2026-05-07). **`gemini-3.1-flash-lite-preview` was shut down 2026-05-25** → use the stable id. Gemma 4 available in Model Garden. | ai.google.dev/gemini-api/docs/models; firebase.google.com/docs/ai-logic/models |
| Gemini embedding model | `gemini-embedding-001` (GA), default 3072 dims, MRL truncation to 768/1536/3072, manual L2-normalize for <3072. `text-embedding-004` deprecated 2026-01-14. | ai.google.dev/gemini-api/docs/embeddings |
| Memorystore for Redis | Vector search native in engine (FLAT+HNSW) for Redis 7.2+; `FT.CREATE`/`FT.SEARCH` compatible with `redis-py` dialect 2; **no third-party modules**. | cloud.google.com/memorystore/docs/redis/{about-vector-search,supported-versions,ftcreate,ftsearch} |
| Cloud Tasks | HTTP target + `OidcToken(service_account_email, audience)`; invoker SA needs `run.invoker` on target + `actAs`. | cloud.google.com/tasks/docs; google-cloud-tasks types |
| Pub/Sub | Pull (recommended high-level StreamingPull) vs push subscriptions. | cloud.google.com/pubsub/docs/pull |
| Cloud SQL connector | `create_async_connector(refresh_strategy="lazy")`, `ip_type=PRIVATE`, `[asyncpg]` extra; private IP needs VPC access. | github GoogleCloudPlatform/cloud-sql-python-connector |
| Cloud Run Jobs | `gcloud run jobs create --command ... --set-secrets ... --set-cloudsql-instances ... --execute-now/--wait`; jobs have **no** min-instances. Services use `--min-instances` to avoid cold starts. | cloud.google.com/run/docs (jobs, migrations blog) |
| Serverless VPC Access | `gcloud compute networks vpc-access connectors create ... --range=10.8.0.0/28`; required for Cloud Run → private IP. | codelabs connecting-to-private-cloudsql-from-cloud-run |

---

## 14. Open questions / confirmations for the user

1. **Q1 — Redis Stream as event log in cloud?** Recommended: **dual-write** in `GcpEventBus`
   (publish to Pub/Sub *and* `XADD` to Memorystore) so you keep a durable, replayable feed and
   `/seed` clean-reset semantics, at negligible cost. Alternative: **Pub/Sub-only** events in
   cloud (drop the Redis Stream replay), simpler but loses replay/`from_id="0"`. **Default:
   dual-write. Confirm.**
2. **Q2 — SSE fan-out at scale.** For the demo, `api-broker` runs single-instance
   (`--min/--max-instances=1`) so one Pub/Sub pull subscription feeds all SSE clients. If you
   want `/feed` to scale horizontally, switch to per-instance subscriptions (create on
   startup, delete on shutdown). **Default: single instance for the demo. Confirm.**
3. **Q3 — Terraform vs gcloud scripts.** Recommendation for a solo dev: **a thin, committed
   `deploy/*.sh` (gcloud) plus a Makefile**, not full Terraform — fastest to iterate, no state
   backend to babysit, and the resource set is small/stable. Provide a minimal Terraform
   module later only if the project outlives the hackathon. **Confirm gcloud-scripts.**
4. **Q4 — embedding model & dim.** Default `gemini-embedding-001` @ `output_dimensionality=768`
   with manual L2 norm, keeping `VECTOR_DIM=768` and the existing index. Alternative:
   `gemini-embedding-2` (auto-normalizes, multimodal) if you want the newest model — would
   change DIM and require an index rebuild. **Confirm 001 @ 768.**
5. **Q5 — model ids in the seed roster.** `gemini-3.1-flash-lite-preview` (in the current seed
   roster) is **shut down**; use stable `gemini-3.1-flash-lite`. OpenAI's current default in
   SDK examples is the `gpt-5.5` family (the plan/seed use `gpt-4.1`/`gpt-4.1-mini`). These are
   code-level seed values (not changed by this doc pass) — **confirm the exact ids available on
   your GCP project / OpenAI account before the live run.**
6. **Q6 — Cloud SQL connectivity choice.** Default: Cloud SQL **Python Connector** (private IP
   + VPC connector). Alternative: Auth Proxy via `--set-cloudsql-instances` (Unix socket).
   **Confirm the connector.**
7. **Q7 — agent auth.** Agent services deployed `--no-allow-unauthenticated` (only Cloud Tasks
   via OIDC can invoke). Public API routes are `--allow-unauthenticated` for the demo. Confirm
   you don't need IAP/API-key on the public routes for the hackathon.
8. **Q8 — Cloud Tasks result callback vs results queue.** Default: agent POSTs the result
   directly to `api-broker /internal/runs/result` (OIDC). Optionally route results through a
   second Cloud Tasks queue (`run-results`) for durability/retry. **Default: direct callback.**
```
