# Agent Bazaar: Build Documentation

A self-organizing agent marketplace where worker agents advertise capabilities, a broker hires the best ones for incoming tasks, and reputation plus credits decide who thrives and who gets starved out. The market improving and the agents improving are the same loop: good agents get hired more, earn credits, and reinvest those credits into upgrading themselves.

Built for WeaveHacks 4 (Multi-Agent Orchestration). Two headline mechanisms: market selection and agent upgrades. Gap-driven agent synthesis is designed for but not built in the first pass.

---

## 1. System Overview

### The loop

1. A user posts a goal.
2. The broker decomposes the goal into subtasks.
3. For each subtask, the broker searches the registry for agents whose advertised capability matches, ranks candidates by semantic fit plus reputation minus price, and hires one.
4. The hired agent executes the subtask.
5. The judge scores the output against the subtask.
6. The ledger updates the agent's reputation and credit balance from the score.
7. When an agent's credits cross a threshold, it reinvests in an upgrade (stronger model, extra tool, or a price bump).
8. Across a stream of tasks the market converges on strong performers, and upgrades push the strong ones further ahead.

### Component map

| Component | Responsibility | Primary tech |
|---|---|---|
| Agent runtime | Defines and executes worker agents, one per container | Agent framework chosen per use case, Vertex AI models, wrapped in Weave |
| Seed agents | The starting roster of distinct specialists | One Cloud Run service each |
| Judge | Scores each execution against its subtask | Single LLM call, structured output, Weave traced |
| Broker | Decomposes goals, matches and ranks candidates, hires | Python service, Redis vector search |
| Registry | Source of truth for agents, reputation, credits | Redis hashes plus vector index |
| Ledger | Updates reputation and credits, triggers upgrades | Python module over Redis |
| Event feed | Streams every market event to the frontend | Redis Stream plus SSE endpoint |
| API layer | Task submission, roster, feed | FastAPI on Cloud Run |
| Dashboard | The live trading floor UI | CopilotKit, AG-UI, React |
| Observability | Traces every call, renders improvement curves | Weave |

---

## 2. Technology Stack

| Layer | Choice | Why |
|---|---|---|
| Agent framework | Decided per use case | Kept open. The agent base class is the only code that binds to it, so the choice can be made per agent without touching the broker or market |
| Models and embeddings | Vertex AI | GCP suite available, gives a real upgrade path (model swap) and managed embeddings |
| Market state | Redis (registry, vector search, ledger, stream) | Sponsor track, single source of truth, vector search is the hiring engine |
| Backend services | FastAPI in Python | Fast to write, async, native SSE |
| Compute | Cloud Run | One service for the broker and API, one service per agent, all stateless |
| Observability | Weave | Host tool, renders the self-improvement curve for the demo |
| Frontend | CopilotKit plus React | Sponsor track, generative UI over AG-UI for a live trading floor |
| Build assist | Cursor | Sponsor tool, just code in it |

Decisions locked: Redis is the only datastore. No Pub/Sub in the first pass, the Redis Stream carries all events. Vertex AI serves both chat models and embeddings so there is one provider to manage. Each agent runs as its own Cloud Run service for a clean, isolated execution environment. The agent framework is left open and chosen per use case, behind a fixed base class interface.

---

## 3. The Contract (build this first, everything depends on it)

The two integration surfaces are the event schema (backend to frontend) and the Redis schema (AI engineer 1 to AI engineer 2). Lock both before writing feature code. Once locked, all three people work fully in parallel against mocks.

### 3.1 Event feed schema

The server pushes these JSON events. The frontend renders them. Hand the frontend dev a static file with one sample of each on day one.

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

Every event also carries `ts` (timestamp) and `event_id`.

### 3.2 API contract

| Method | Path | Purpose | Returns |
|---|---|---|---|
| GET | /agents | Full roster | list of agent objects |
| POST | /task | Submit a goal, body {goal} | {task_id} |
| GET | /feed | SSE stream of events | text/event-stream |
| POST | /seed | Reset market to fresh state for the demo | {ok} |

Agent object shape:

```json
{
  "agent_id": "writer-01",
  "name": "Copywriter",
  "skills": ["writing", "summarization"],
  "capability_text": "Writes and summarizes marketing and technical copy",
  "model": "gemini-flash",
  "tools": [],
  "reputation": 0.5,
  "credits": 100,
  "price": 5,
  "hires": 0,
  "wins": 0
}
```

---

## 4. Module Specifications

Each module below lists what it does, the tech, how to build it, and what it reads or writes. Build order and parallelism are in Section 8.

### 4.1 Redis Registry and Vector Index

What it does: stores every agent, holds the capability vector index that powers hiring, and exposes the leaderboard.

Tech: Redis with the vector search module (RediSearch), Vertex AI text embeddings for the capability vectors.

How to build:
- Store one hash per agent at key `agent:{id}` with the fields from the agent object.
- On agent creation, embed `capability_text` with Vertex AI and store the vector on the hash.
- Create a vector index over those embeddings for KNN search.
- Maintain a sorted set `leaderboard` scored by reputation for a free, always-sorted roster view.

| Structure | Key | Holds |
|---|---|---|
| Hash per agent | agent:{id} | all agent fields plus capability vector |
| Vector index | agents_idx | KNN over capability vectors |
| Sorted set | leaderboard | agent_id scored by reputation |
| Hash per task | task:{id} | goal, subtasks, status |
| Stream | market:feed | every event from Section 3.1 |

Reads and writes: written by the seeder and the ledger, read by the broker.

### 4.2 Agent Runtime and Base Class

What it does: defines a worker agent and executes a subtask, returning an output. Each agent runs as its own Cloud Run service. Every execution is traced.

Tech: a thin HTTP wrapper (FastAPI) around an agent implementation, Vertex AI model, Weave decorator on the execute path. The agent framework inside is chosen per use case and is not fixed here.

How to build:
- Define a base contract every agent service honors, independent of the framework used inside: an HTTP endpoint `POST /run` that takes `{subtask_text, config}` and returns `{output}`. This contract is the only thing the broker knows about an agent, so the internal framework (Strands, LangGraph, plain function-calling, or anything else) can differ per agent and be decided when you know the agent's job.
- Provide a small base class or template that handles the HTTP wrapper, config loading, the Weave decorator, and the Vertex AI client, so a new agent is just a system prompt, a model, and optional tools dropped into the template.
- Wrap the execute path with the Weave op decorator so every run is traced with inputs, outputs, and the model used.
- Keep agents stateless. All persistent state lives in Redis. Statelessness is what lets each agent run as its own Cloud Run service and scale to zero between calls.

Reads and writes: receives its config in the request from the broker, writes nothing directly (the ledger handles state).

### 4.2a Agent Service Registry (service URLs)

What it does: maps each agent_id to the Cloud Run URL of its service, so the broker knows where to send a hire.

Tech: a field on the agent hash in Redis (`service_url`), set at deploy or seed time.

How to build:
- When an agent service is deployed, record its Cloud Run URL on `agent:{id}`.
- The broker reads `service_url` after it picks a winner and calls that service's `POST /run`.
- For local development, point `service_url` at a localhost port so the same broker code works without deploying.

Reads and writes: written by the seeder or deploy step, read by the broker at hire time.

### 4.3 Seed Agents

What it does: provides the starting roster of 5 to 8 distinct specialists so the market has variety to select from.

Tech: each agent is its own service built from the base template (4.2), deployed to Cloud Run, and registered into Redis by the seeder.

How to build:
- Define distinct capability profiles, for example: copywriter, code generator, data summarizer, fact checker, translator, planner, math solver, formatter. Each becomes one Cloud Run service from the base template.
- Give a couple of them deliberately weaker configs (cheaper model, vaguer prompt) so the demo shows a weak agent getting starved.
- Spread initial prices and keep starting reputation equal so divergence is earned, not seeded.
- The seeder writes each agent's hash including its `service_url` and capability vector. To keep eight deploys manageable, use one container image parameterized by an env var or config, not eight separate codebases.

Reads and writes: agent services deployed to Cloud Run, agent records written into Redis by the seeder.

### 4.4 Broker

What it does: the heart of the market. Decomposes a goal, finds and ranks candidates per subtask, hires, dispatches execution, and emits events.

Tech: FastAPI background task or worker loop, Vertex AI for decomposition, Redis vector search for matching.

How to build:
- Decompose: one LLM call turns the goal into an ordered list of subtasks. Emit `task_posted`.
- Match: embed each subtask, run KNN against the agent index to get top candidates with a match score.
- Rank: compute `final_score = w1 * match + w2 * reputation - w3 * price`. Keep the weights as simple constants. Emit `candidates_ranked`.
- Hire: pick the top candidate, emit `agent_hired`, read its `service_url` and call that agent service's `POST /run` over HTTP with the subtask and config.
- After execution, emit `task_executed`, then pass the output to the judge.

Reads and writes: reads the registry and vector index, calls agent services over HTTP, writes events to the stream.

### 4.5 Judge

What it does: scores how well an output satisfied its subtask, returning a number the ledger can act on.

Tech: single Vertex AI call with structured output, Weave traced.

How to build:
- Prompt the judge with the subtask and the output, ask for a score from 0 to 1 plus a one line reason.
- Force structured JSON output so parsing never breaks the loop.
- Emit `task_scored`.
- Keep it cheap and fast, it runs on every execution.

Reads and writes: reads nothing from Redis, returns the score to the broker which forwards it to the ledger.

### 4.6 Ledger (reputation and credits)

What it does: turns a judge score into updated reputation and credits, and decides when an agent can upgrade.

Tech: Python module over Redis, atomic updates.

How to build:
- Reputation: exponential moving average, `new = alpha * score + (1 - alpha) * old`, alpha around 0.3 so it moves visibly but not wildly. Update the leaderboard sorted set. Emit `reputation_changed`.
- Credits: award credits proportional to the judge score and the agent's price (it earned its fee). Emit `credits_changed`.
- After each update, check the upgrade threshold and hand off to the upgrade module if crossed.
- Increment `hires` and `wins` (a win is a score above a cutoff) for display.

Reads and writes: reads and writes agent hashes and the leaderboard, writes events.

### 4.7 Upgrade Logic

What it does: the second headline. When an agent has enough credits, it spends them to improve itself.

Tech: Python, swaps fields on the agent hash, re-embeds if capability text changes.

How to build:
- On crossing the credit threshold, pick an upgrade: swap to a stronger Vertex AI model, add a tool to its config, or raise its price because it is in demand.
- Keep the upgrade a change to the agent's config in Redis, not a redeploy. The broker passes config in the `POST /run` request, so the agent service reads its current model and tools from that config each call. This means an upgrade takes effect on the very next hire with no Cloud Run redeploy, which keeps the demo instant and avoids deploy latency on stage.
- Deduct the cost from credits.
- If the upgrade changes what the agent can do, update `capability_text` and re-embed so future matching reflects it.
- Emit `agent_upgraded`.

The clean demo beat: an agent earns its way to a model swap, then visibly climbs the leaderboard faster afterward. That closes the loop between market improvement and agent improvement.

Design seam for later: the same code path that creates or modifies an agent is what gap-driven synthesis will reuse. Keep agent creation in one function so synthesis is a later caller, not a rewrite.

Reads and writes: reads and writes the agent hash and vector index, writes events.

### 4.8 Event Feed and Streaming

What it does: gets every market event from the backend to the dashboard in real time.

Tech: Redis Stream as the buffer, FastAPI SSE endpoint as the transport.

How to build:
- Every module that emits an event appends a JSON entry to the `market:feed` stream. Centralize this in one `emit(event)` helper so nobody hand-rolls stream writes.
- The `/feed` endpoint reads new entries from the stream and forwards them as server sent events.
- The stream doubles as a replay log, useful for re-running the demo without re-running the market.

Reads and writes: every module writes, the API reads.

### 4.9 API Layer

What it does: the public surface for the frontend and the demo controls.

Tech: FastAPI on Cloud Run.

How to build:
- Implement the four endpoints from Section 3.2.
- `/task` enqueues work and returns immediately, the broker runs it in the background.
- `/seed` wipes and reloads the market so you can demo from a clean state on stage.
- Enable CORS for the frontend origin.

Reads and writes: reads the registry, writes tasks, triggers the broker.

### 4.10 Dashboard (frontend)

What it does: the live trading floor. Shows the roster with reputation and credit bars, the event feed as it streams, the leaderboard, and a box to post a goal.

Tech: React, CopilotKit, AG-UI, consuming the SSE feed.

How to build:
- Build entirely against the static mock event file first, so this is done before the backend is live.
- Render four panels: roster (with live reputation and credit bars), live feed of events, leaderboard, and a task input.
- Use generative UI to surface auctions and hires as they happen, and animate reputation bars and the upgrade moment so they read clearly on a projector.
- Subscribe to `/feed`, switch from mock to live by changing one URL.

Reads and writes: reads `/agents` and `/feed`, posts to `/task`.

### 4.11 Observability (Weave)

What it does: traces every model call and renders the success-rate-up, cost-per-task-down curve that proves self-improvement to the judges.

Tech: Weave, decorators on agent execute, judge, broker decompose.

How to build:
- Initialize Weave once at service start.
- Decorate every LLM-calling function so traces capture inputs, outputs, model, latency, and cost.
- Log custom metrics per task: judge score, cost, which agent was hired. Build a Weave view that plots rolling success rate and cost per task over the task stream.
- This is mandatory regardless of anything else, it is the host tool and it is how the demo lands.

---

## 5. Data Flow (one task, end to end)

1. Frontend posts a goal to `/task`. API stores `task:{id}`, returns the id, kicks the broker.
2. Broker decomposes, emits `task_posted`.
3. Per subtask: broker embeds it, KNN against `agents_idx`, ranks, emits `candidates_ranked`, hires top, emits `agent_hired`.
4. Broker calls the hired agent's Cloud Run service over HTTP, the agent executes and returns its output, broker emits `task_executed`.
5. Judge scores, emits `task_scored`.
6. Ledger updates reputation and credits, emits `reputation_changed` and `credits_changed`, updates leaderboard.
7. If threshold crossed, upgrade runs, emits `agent_upgraded`.
8. All events flow through `market:feed` to `/feed` to the dashboard, which animates the changes. Weave records every model call.

---

## 6. Cloud and Deployment (GCP)

| Concern | Service | Notes |
|---|---|---|
| Broker and API | Cloud Run | One service, stateless, scales to zero between demos |
| Agent execution | Cloud Run, one service per agent | Each agent is its own container for a clean, isolated execution environment. Use a single parameterized image so eight agents are eight deploys of one codebase, not eight codebases |
| Models and embeddings | Vertex AI | Chat models for agents, judge, decomposition, plus the embedding model for matching |
| Market state | Redis | Managed Redis (Memorystore) or the Redis Cloud free tier the sponsor provides, prefer the sponsor instance for the partner track |
| Service discovery | Redis | The `service_url` field on each agent hash, set at deploy time, is how the broker finds an agent |
| Secrets | Secret Manager | Redis URL, Vertex credentials |
| Container build | Cloud Build or local Docker push to Artifact Registry | Whichever is faster on the day |

Deployment order: get Redis reachable, deploy the agent image once per agent (each with its config and recording its `service_url` into Redis), deploy the API and broker, point the frontend at the Cloud Run URL.

How per-agent containers work here:
- One agent image, parameterized by config (model, system prompt, tools, skills, price) passed via env var or fetched on startup. Deploying agent number two is the same image with different config, not new code.
- Each deploy records its Cloud Run URL into the agent's Redis hash as `service_url`. The broker reads that to dispatch a hire.
- Agents are stateless and scale to zero, so idle agents cost nothing and a hire spins the container up on demand.
- Keep a local-run path: run each agent on a localhost port and set `service_url` to that port, so the broker code is identical locally and in the cloud. Develop locally, deploy to Cloud Run only for the live demo.

Watch the cold start: scale-to-zero means the first hire of an idle agent pays a startup cost. For the demo, hit each agent once during setup to warm them, or set a minimum of one instance on the few agents your demo batch will exercise.

---

## 7. Demo Flow

1. Hit `/seed`. Fresh market, all reputations equal.
2. Fire a prepared batch of varied goals.
3. Reputations diverge live on the dashboard. A weak agent stops getting hired.
4. A strong agent crosses the credit threshold, upgrades its model, and pulls further ahead.
5. Cut to the Weave view: rolling success rate rising, cost per task falling across the task stream.

That is the full story in about 90 seconds. The dashboard shows the market improving, the upgrade event shows agents improving, and Weave proves both with numbers.

---

## 8. Build Order and Parallelism

### Phase 0: lock contracts (all three together, do not skip)

Agree on the event schema (3.1), the API contract (3.2), and the Redis schema (4.1). Produce the static mock event file. After this, the three tracks below run fully in parallel.

### Track A: AI engineer 1 (runtime side)

| Order | Item | Depends on |
|---|---|---|
| A1 | Weave init and decorator pattern | Phase 0 |
| A2 | Agent service base template: HTTP `POST /run` wrapper, config loading, Vertex client, Weave decorator (4.2) | A1 |
| A3 | Define the 5 to 8 seed agent configs, run them locally on localhost ports (4.3) | A2 |
| A4 | Judge (4.5) | A1 |
| A5 | Deploy the agent image once per agent to Cloud Run, record each `service_url` (4.2a, 6) | A3, and Redis schema from B1 |
| A6 | Custom Weave metrics view for the curve (4.11) | A2, A4 |

### Track B: AI engineer 2 (market side)

| Order | Item | Depends on |
|---|---|---|
| B1 | Redis registry, vector index, seeder, emit helper, `service_url` field (4.1, 4.2a, 4.8) | Phase 0 |
| B2 | Broker: decompose, match, rank, hire by HTTP call to `service_url` (4.4) | B1 |
| B3 | Ledger: reputation and credits (4.6) | B1 |
| B4 | API layer and SSE feed (4.9) | B1 |
| B5 | Upgrade logic as a config change in Redis (4.7) | B3 |

### Track C: frontend (entire first day against the mock)

| Order | Item | Depends on |
|---|---|---|
| C1 | Roster, feed, leaderboard, task input against mock (4.10) | Phase 0 mock file |
| C2 | Animations for reputation bars and the upgrade moment | C1 |
| C3 | Switch SSE URL from mock to live `/feed` | B4 done |

### Integration points

- First integration: Track A's agent template (A2) running on a localhost port plus Track B's broker (B2) and registry (B1) run one task end to end, broker hiring over HTTP. This is the earliest moment the loop is real, and it does not need Cloud Run yet since `service_url` can point at localhost.
- Second integration: ledger (B3) closes the loop so reputation moves, then frontend flips to live (C3).
- Third integration: upgrade (B5) and the Weave curve (A6) land for the demo.
- Cloud cutover: deploy agents to Cloud Run (A5) and repoint each `service_url` from localhost to the Cloud Run URL. Because the broker only knows the URL, nothing in B2 changes.

### What can run in parallel right away

Everything after Phase 0. A1, A2, A4 on one machine. B1 through B4 on another. C1, C2 on the third. Agents run locally on ports during development, so neither AI engineer is blocked on Cloud Run. The only hard cross-track dependencies are the Redis schema (B1) feeding A5, and the live feed (B4) feeding C3, both of which the mock and the agreed schema let you defer. Treat the Cloud Run deploy (A5) as a cutover step near the end, not a prerequisite for building the loop.

### Stretch: gap-driven synthesis (only if ahead)

A meta-agent watches for subtasks where the best candidate's match score is below a floor, then calls the same agent-creation function the upgrade module already uses to spin up a new specialist with a fitting capability profile. Because agent creation is one function (4.7 design seam), this is additive, not a rewrite.

---

## 9. Risk Notes

| Risk | Mitigation |
|---|---|
| Economy tuning eats hours | Keep ranking weights and the reputation alpha as fixed constants, do not build a tuning UI |
| Per-agent Cloud Run cold start | Warm the few demo agents before presenting, or set minimum one instance on them. Develop against localhost so deploy is a late cutover, not a blocker |
| Eight deploys is fiddly | One parameterized image, deployed per agent with different config, not eight codebases |
| Judge inconsistency breaks the curve | Force structured output, keep the judge prompt short and fixed |
| Frontend blocked on backend | Mock event file from Phase 0, build the whole dashboard against it |
| Demo fails live | `/seed` for a clean reset, and the Redis Stream as a replay log so you can re-run from recorded events |