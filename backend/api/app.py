"""FastAPI application: agents, task posting, SSE feed, seed."""

import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from contracts.schemas import UserPublic
from backend.config import API_URL, USER_START_CREDITS
from backend.sim import runner as sim_runner
from backend.db import repo
from backend.db.models import Model as ModelORM
from backend.infra.db import get_session, session_scope
from backend.infra.redis_client import close_redis, get_redis
from backend.infra.weave_init import init_weave
from backend.market import broker, portfolio, pricing, registry, seeder, trading
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


class TradeBody(BaseModel):
    user_id: str
    model_id: str
    side: Literal["buy", "sell"]
    amount: float


class TradeResponse(BaseModel):
    trade_id: str
    price: float
    shares: float
    credits: float


class CreateUserBody(BaseModel):
    name: str
    email: str | None = None
    is_sim: bool = False


class CreateUserResponse(BaseModel):
    user_id: str


class SimStartBody(BaseModel):
    n_posters: int | None = None
    n_investors: int | None = None
    cadence_s: float | None = None


class MarketResponse(BaseModel):
    models: list[dict]
    history: list[dict]


def model_to_public(m: ModelORM, price: float) -> dict:
    return {
        "model_id": m.model_id,
        "name": m.name,
        "provider": m.provider,
        "tier": m.tier,
        "price": price,
        "shares": float(m.pool_shares),
        "credits": float(m.pool_credits),
        "executable": m.executable,
    }


async def _list_public_models(session) -> list[dict]:
    r = get_redis()
    out = []
    for m in await repo.list_models(session):
        price = await registry.get_model_price(r, m.model_id)
        if price is None:
            price = float(m.pool_credits) / float(m.pool_shares)
        out.append(model_to_public(m, price))
    return out


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


@app.post("/sim/start")
async def sim_start(body: SimStartBody | None = None):
    params = body.model_dump(exclude_none=True) if body else {}
    await sim_runner.start(API_URL, **params)
    return {"ok": True}


@app.post("/sim/stop")
async def sim_stop():
    await sim_runner.stop()
    return {"ok": True}


@app.get("/models")
async def get_models(session=Depends(get_session)):
    return await _list_public_models(session)


@app.get("/market", response_model=MarketResponse)
async def get_market(session=Depends(get_session)):
    r = get_redis()
    models = await _list_public_models(session)
    hist = await registry.read_price_history(r, count=500)
    return MarketResponse(models=models, history=hist)


@app.post("/trade", response_model=TradeResponse)
async def post_trade(body: TradeBody, session=Depends(get_session)):
    r = get_redis()
    try:
        result = await trading.trade(
            session,
            r,
            user_id=body.user_id,
            model_id=body.model_id,
            side=body.side,
            amount=float(body.amount),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
    return TradeResponse(**result)


@app.get("/portfolio/{user_id}")
async def get_portfolio(user_id: uuid.UUID, session=Depends(get_session)):
    r = get_redis()
    try:
        p = await portfolio.value(session, r, user_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return p.model_dump()


@app.post("/users", response_model=CreateUserResponse)
async def post_user(body: CreateUserBody, session=Depends(get_session)):
    email = body.email or f"{uuid.uuid4().hex}@bazaar.local"
    u = await repo.create_user(
        session,
        email=email,
        name=body.name,
        credits=USER_START_CREDITS,
        is_sim=body.is_sim,
    )
    await session.commit()
    return CreateUserResponse(user_id=str(u.id))


@app.get("/users")
async def get_users(session=Depends(get_session)):
    r = get_redis()
    out = []
    for u in await repo.list_users(session):
        try:
            p = await portfolio.value(session, r, u.id)
        except KeyError:
            continue
        out.append(
            UserPublic(
                user_id=str(u.id),
                name=u.name,
                email=u.email,
                credits=p.credits,
                is_sim=u.is_sim,
                net_worth=p.total,
            ).model_dump()
        )
    out.sort(key=lambda x: x["net_worth"], reverse=True)
    return out
