"""
Seed roster — tiered specialist agents loaded from data/capabilities.json.

Each capability family may expose pro / flash / lite variants with fixed models
and derived hire prices. Workers are generic; the broker passes per-dispatch
model config.
"""

from contracts.schemas import Agent
from backend.config import AGENT_WORKER_BASE_PORT, AGENT_WORKERS
from backend.market.capabilities import (
    SUGGESTED_PROMPTS,
    build_agents_by_capability,
    build_tiered_roster,
)

SEED_AGENTS: list[Agent] = build_tiered_roster()

AGENTS_BY_CAPABILITY: dict[str, list[Agent]] = build_agents_by_capability(SEED_AGENTS)

# Assign every agent a service_url from the shared worker pool (round-robin).
_WORKER_URLS = [
    f"http://localhost:{AGENT_WORKER_BASE_PORT + i}" for i in range(max(1, AGENT_WORKERS))
]
for _i, _agent in enumerate(SEED_AGENTS):
    _agent.service_url = _WORKER_URLS[_i % len(_WORKER_URLS)]
