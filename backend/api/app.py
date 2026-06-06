"""FastAPI application: agents, task posting, SSE feed, seed."""

import asyncio
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from backend.db import repo
from backend.infra.db import get_session, session_scope
from backend.infra.redis_client import close_redis, get_redis
from backend.infra.weave_init import init_weave
from backend.market import broker, pricing, seeder
from backend.ports.factory import get_event_bus

bus = get_event_bus()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_weave()
    yield
    await close_redis()


app = FastAPI(title="Agent Bazaar API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TaskBody(BaseModel):
    goal: str
    user_id: str | None = None


class RunResultBody(BaseModel):
    subtask_id: str
    agent_id: str
    output: str
    task_id: str


async def _run_task(task_id: str, goal: str) -> None:
    async with session_scope() as session:
        r = get_redis()
        await broker.run_task(r, session, task_id, goal)


@app.get("/agents")
async def get_agents(session=Depends(get_session)):
    r = get_redis()
    out = []
    for a in await repo.list_agents(session):
        mp = await pricing.model_price(r, a.model)
        a.price = pricing.derived_price(mp, a.margin)
        out.append(a.model_dump(exclude={"service_url"}))
    return out


@app.post("/task")
async def post_task(body: TaskBody, session=Depends(get_session)):
    user_uuid = uuid.UUID(body.user_id) if body.user_id else None
    task = await repo.create_task(session, goal=body.goal, user_id=user_uuid)
    await session.commit()
    task_id = str(task.id)
    asyncio.create_task(_run_task(task_id, body.goal))
    return {"task_id": task_id}


@app.get("/feed")
async def feed_sse():
    async def gen():
        async for _cursor, ev in bus.subscribe(from_id="$"):
            yield {"event": ev.type, "data": ev.model_dump_json()}

    return EventSourceResponse(gen())


@app.post("/seed")
async def post_seed():
    counts = await seeder.seed()
    return {"ok": True, **counts}


@app.post("/internal/runs/result")
async def run_result(body: RunResultBody, session=Depends(get_session)):
    r = get_redis()
    await broker.handle_run_result(
        r,
        session,
        subtask_id=body.subtask_id,
        agent_id=body.agent_id,
        output=body.output,
        task_id=body.task_id,
    )
    await session.commit()
    return {"ok": True}


@app.get("/healthz")
async def healthz():
    return {"ok": True}
