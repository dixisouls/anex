"""Agent base service — A2A-compliant FastAPI app.

Each agent exposes:
  GET  /.well-known/agent.json  ->  AgentCard (A2A capability declaration)
  POST /tasks/send              ->  A2ATaskResult (A2A task execution)
  GET  /healthz                 ->  liveness probe

The agent is self-describing: it resolves its own model, provider, and
system prompt from seed data using the AGENT_ID env var. The orchestrator
may override any of these via task.metadata["config"].
"""

import os

import weave
from fastapi import FastAPI

from contracts.a2a import (
    A2ATask,
    A2ATaskResult,
    AgentCard,
    AgentCapabilities,
    AgentSkill,
)
from backend.infra.model_router import generate
from backend.infra.weave_init import init_weave


def _resolve_config(agent_id: str, metadata: dict) -> dict:
    """Return model config, preferring metadata override then seed defaults."""
    if "config" in metadata:
        return metadata["config"]
    from backend.market.seed_agents import SEED_AGENTS, SUGGESTED_PROMPTS

    agent = next((a for a in SEED_AGENTS if a.agent_id == agent_id), None)
    if agent is None:
        return {"model": os.getenv("GCP_CHAT_MODEL", "gemini-3.5-flash"), "provider": "gcp"}
    return {
        "model": agent.model,
        "provider": _infer_provider(agent.model),
        "system": SUGGESTED_PROMPTS.get(agent_id),
        "tools": agent.tools,
    }


def _infer_provider(model_id: str) -> str:
    from backend.market.seed_models import SEED_MODELS

    for m in SEED_MODELS:
        if m["model_id"] == model_id:
            return m["provider"]
    return "gcp"


def _build_agent_card(agent_id: str, base_url: str) -> AgentCard:
    from backend.market.seed_agents import SEED_AGENTS

    agent = next((a for a in SEED_AGENTS if a.agent_id == agent_id), None)
    if agent is None:
        return AgentCard(name=agent_id, description=agent_id, url=base_url)

    skills = [
        AgentSkill(
            id=f"{agent_id}/{s.lower().replace(' ', '-')}",
            name=s,
            description=s,
            tags=agent.skills,
        )
        for s in agent.skills
    ]
    return AgentCard(
        name=agent.name,
        description=agent.capability_text,
        url=base_url,
        capabilities=AgentCapabilities(),
        skills=skills,
    )


def build_app(agent_id: str) -> FastAPI:
    init_weave()
    app = FastAPI(title=f"agent:{agent_id}")

    port = int(os.environ.get("PORT", "9001"))
    base_url = f"http://localhost:{port}"

    @app.get("/.well-known/agent.json", response_model=AgentCard)
    async def agent_card():
        return _build_agent_card(agent_id, base_url)

    @weave.op
    def execute(text: str, config: dict) -> dict:
        return generate(
            config["model"],
            config["provider"],
            text,
            config.get("system"),
        )

    @app.post("/tasks/send", response_model=A2ATaskResult)
    async def tasks_send(task: A2ATask):
        config = _resolve_config(agent_id, task.metadata)
        text = task.message.text()
        try:
            result = execute(text, config)
            return A2ATaskResult.completed(task.id, result["output"])
        except Exception as exc:
            return A2ATaskResult.failed(task.id, str(exc))

    @app.get("/healthz")
    async def healthz():
        return {"ok": True, "agent_id": agent_id}

    return app
