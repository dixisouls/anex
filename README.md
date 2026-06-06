# Agent Bazaar

A self-organizing agent marketplace. Worker agents advertise capabilities, a broker hires the best fit for each incoming subtask, and reputation plus credits decide who thrives and who gets starved out. Market improvement and agent improvement are the same loop: good agents get hired more, earn credits, and reinvest them into upgrading themselves.

Built for WeaveHacks 4 (Multi-Agent Orchestration).

## The loop

A user posts a goal. The broker decomposes it into subtasks, searches the registry for agents whose advertised capability matches, ranks them by semantic fit plus reputation minus price, and hires one. The agent executes, a judge scores the output, and the ledger updates the agent's reputation and credits. When an agent crosses a credit threshold it reinvests in an upgrade (stronger model, extra tool, or a price bump). Across a stream of tasks the market converges on strong performers.

## Structure

- `contracts/` Shared integration surfaces. Event schema, API contract, Redis schema, and the static mock event file. Source of truth for all three tracks.
- `agent/` Worker agent base template and the seed agent configs. One stateless service per agent.
- `market/` The market backend. Registry and vector index, broker, judge, ledger, upgrade logic, API and SSE feed.
- `frontend/` The live trading floor dashboard (Next.js, CopilotKit, AG-UI).

## Stack

Vertex AI for models and embeddings, Redis for all market state (registry, vector search, ledger, event stream), FastAPI services on Cloud Run, Weave for tracing and the improvement curve, Next.js plus CopilotKit on the frontend.

## Local development

```
python -m venv venv
source venv/bin/activate
# install per-track requirements once they exist:
# pip install -r market/requirements.txt
# pip install -r agent/requirements.txt

cd frontend && npm install && npm run dev
```

Agents run on localhost ports during development. Cloud Run is a late cutover step for the live demo, not a prerequisite for building the loop.

## Build order

Lock the three contracts in `contracts/` first. Everything else keys off them. After that the agent, market, and frontend tracks run fully in parallel against the mock event file.