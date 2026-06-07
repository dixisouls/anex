# Anex — Contracts

The `contracts/` package is the **shared contract layer**: the typed objects that cross
subsystem boundaries (broker, agents, exchange, ledger, API, simulation, frontend). It has
no business logic and no dependencies on the rest of the backend — everything else imports
*from* it. All types are Pydantic v2.

Keeping these shapes in one dependency-free package is what lets the broker, the A2A
workers, the API, and the simulation agree on the wire format without importing each other.

| Module | Defines | Used by |
|--------|---------|---------|
| [`a2a.py`](a2a.py) | The **Google A2A protocol** types | Agent workers + broker dispatch |
| [`events.py`](events.py) | The **market event** discriminated union | Event bus, SSE feed, frontend |
| [`schemas.py`](schemas.py) | **Core data objects** | Broker, registry, exchange, API responses |

---

## `a2a.py` — Agent-to-Agent protocol

Implements the core [Google A2A spec](https://google.github.io/A2A) types used for task
delegation. Every Anex worker is A2A-compliant; the broker hires by speaking A2A.

| Type | Role |
|------|------|
| `AgentCard` | Capability declaration served at `GET /.well-known/agent.json` (name, description, capabilities, skills) |
| `AgentSkill`, `AgentCapabilities` | Components of the card |
| `A2ATask` | The unit of work sent to `POST /tasks/send` — a `Message` of `TextPart`s plus `metadata` (Anex passes the per-dispatch model config here) |
| `A2ATaskResult` | The response — a `TaskStatus` plus output `Artifact`s; helpers `completed()` / `failed()` |
| `Message`, `TextPart`, `Artifact` | Content primitives |
| `TaskState`, `TaskStatus` | The task state machine (`submitted → working → completed | failed | canceled | input-required`) |

See [hybrid A2A](../ARCHITECTURE.md#hybrid-a2a) for how Anex keeps these agent identities
real while pooling execution onto generic workers.

---

## `events.py` — market events

Every meaningful state change is published as a **typed event** on the `market:feed`
stream and replayed to the SSE `/feed` endpoint. Events form a Pydantic **discriminated
union** (`MarketEvent`, keyed on `type`) with a shared base carrying `event_id` and `ts`;
`parse_event()` / `EVENT_ADAPTER` validate inbound JSON.

| Event | Emitted when |
|-------|--------------|
| `task_posted` | A goal is decomposed into subtasks |
| `candidates_ranked` | A subtask's candidate agents are ranked |
| `agent_hired` | An agent is hired for a subtask |
| `subtask_skipped` | No affordable/available agent for a subtask |
| `task_executed` | An agent returns output |
| `task_scored` | The judge scores an output |
| `reputation_changed` / `credits_changed` | Ledger settlement updates an agent |
| `agent_upgraded` | An agent upgrade event |
| `model_listed` | A model stock is listed (IPO) |
| `price_changed` | A model's price moves (trade / earnings / arb) |
| `earnings_injected` | Judge-driven earnings hit a model's pool |
| `trade_executed` | A user buys/sells a model stock |
| `portfolio_changed` | A user's credits/holdings value changes |

---

## `schemas.py` — core data objects

The records that flow between subsystems and out through the API.

| Type | Role |
|------|------|
| `Agent` | The roster record — capability, service tier, model, skills, reputation, credits, margin, derived price |
| `Subtask` | One ordered unit of decomposed work |
| `Candidate` | A ranked agent for a subtask (`match_score`, `reputation`, `price`, `final_score`) |
| `Task` | A posted goal and its decomposition |
| `SubtaskDetail` / `TaskDetail` / `TaskListResponse` | Persisted pipeline state for task history (stage, candidates, hire price, output preview, judge score, skip info) |
| `Model` | A tradable model stock (AMM pool, price, IPO price) |
| `Holding` / `Portfolio` | A user's positions and net worth |
| `UserPublic` | Public-facing user record (credits, net worth, `is_sim`) |
