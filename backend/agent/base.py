"""Agent base service: POST /run contract every seed agent honors."""

from fastapi import FastAPI
from pydantic import BaseModel
import weave

from backend.infra.model_router import generate
from backend.infra.weave_init import init_weave


class RunConfig(BaseModel):
    model: str
    provider: str
    system: str | None = None
    tools: list[str] = []


class RunRequest(BaseModel):
    subtask_text: str
    config: RunConfig


def build_app(agent_id: str) -> FastAPI:
    init_weave()
    app = FastAPI(title=f"agent:{agent_id}")

    @weave.op
    def execute(subtask_text: str, config: RunConfig) -> str:
        return generate(config.model, config.provider, subtask_text, config.system)

    @app.post("/run")
    async def run(req: RunRequest):
        return {"output": execute(req.subtask_text, req.config)}

    @app.get("/healthz")
    async def healthz():
        return {"ok": True, "agent_id": agent_id}

    return app
