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
from backend.api import task_pool
from backend.sim import runner as sim_runner
from backend.db import repo
from backend.db.models import Model as ModelORM
from backend.infra.db import get_session
from backend.infra.passwords import hash_password, verify_password
from backend.infra.redis_client import close_redis, get_redis
from backend.infra.weave_init import init_weave
from backend.market import broker, credits, portfolio, pricing, registry, seeder, trading
from backend.config import GCP_CHAT_MODEL
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
    budget: float | None = None
    broker_model: str | None = None
    preferred_tier: Literal["pro", "flash", "lite"] | None = None


class BuyCreditsBody(BaseModel):
    user_id: str
    amount: float


class BuyCreditsResponse(BaseModel):
    credits: float


class RegisterBody(BaseModel):
    email: str
    password: str
    name: str | None = None


class LoginBody(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    user_id: str
    name: str
    email: str
    credits: float


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


async def _run_task(
    task_id: str,
    goal: str,
    user_id: str,
    budget: float,
    *,
    broker_model: str,
    preferred_tier: str,
) -> None:
    async with task_pool.get_task_semaphore():
        await broker.run_task(
            task_id,
            goal,
            user_id=user_id,
            budget=budget,
            broker_model=broker_model,
            preferred_tier=preferred_tier,
        )


async def _validate_broker_model(session, model_id: str) -> str:
    r = get_redis()
    cached = await registry.get_model_cached(r, model_id)
    if cached is not None:
        return model_id
    models = await repo.list_models(session)
    if any(m.model_id == model_id for m in models):
        return model_id
    raise HTTPException(status_code=400, detail=f"unknown broker model: {model_id}")


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
    if not body.user_id:
        raise HTTPException(status_code=401, detail="login required to post a task")
    try:
        user = await repo.get_user(session, body.user_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="user not found") from exc
    credits = float(user.credits)
    budget = credits if body.budget is None else float(body.budget)
    if budget <= 0:
        raise HTTPException(status_code=400, detail="budget must be positive")
    if budget > credits:
        raise HTTPException(
            status_code=400, detail="budget exceeds available credits"
        )
    broker_model = body.broker_model or GCP_CHAT_MODEL
    await _validate_broker_model(session, broker_model)
    preferred_tier = body.preferred_tier or "pro"
    if preferred_tier not in ("pro", "flash", "lite"):
        raise HTTPException(status_code=400, detail="invalid preferred_tier")
    task = await repo.create_task(session, goal=body.goal, user_id=user.id)
    await session.commit()
    task_id = str(task.id)
    asyncio.create_task(
        _run_task(
            task_id,
            body.goal,
            str(user.id),
            budget,
            broker_model=broker_model,
            preferred_tier=preferred_tier,
        )
    )
    return {
        "task_id": task_id,
        "budget": budget,
        "broker_model": broker_model,
        "preferred_tier": preferred_tier,
    }


@app.post("/credits/buy", response_model=BuyCreditsResponse)
async def buy_credits(body: BuyCreditsBody, session=Depends(get_session)):
    amount = float(body.amount)
    if amount < credits.MIN_BUY_AMOUNT or amount > credits.MAX_BUY_AMOUNT:
        raise HTTPException(
            status_code=400,
            detail=f"amount must be between {credits.MIN_BUY_AMOUNT:g} and {credits.MAX_BUY_AMOUNT:g}",
        )
    try:
        user = await repo.get_user(session, body.user_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="user not found") from exc
    r = get_redis()
    new_balance = await credits.grant_credits(r, user_id=user.id, amount=amount)
    await session.commit()
    return BuyCreditsResponse(credits=new_balance)


@app.get("/feed")
async def feed_sse():
    async def gen():
        r = get_redis()
        from backend.market import feed as feed_mod

        cursor = "0-0"
        backlog = await feed_mod.read_new(r, cursor, count=200)
        for entry_id, ev in backlog:
            cursor = entry_id
            yield {"event": ev.type, "data": ev.model_dump_json()}
        async for _cursor, ev in bus.subscribe(from_id=cursor):
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


@app.get("/task/slots")
async def task_slots():
    """How many broker pipelines can start now (backpressure for sim posters)."""
    return task_pool.task_slots_status()


@app.post("/sim/start")
async def sim_start(body: SimStartBody | None = None):
    """Light demos only; for heavy load use `python -m backend.sim.main` or scripts/run_sim.sh."""
    params = body.model_dump(exclude_none=True) if body else {}
    await sim_runner.start(API_URL, **params)
    return {"ok": True, "note": "For many sims, prefer the external runner: scripts/run_sim.sh"}


@app.post("/sim/stop")
async def sim_stop():
    await sim_runner.stop()
    return {"ok": True}


@app.get("/models")
async def get_models(session=Depends(get_session)):
    return await _list_public_models(session)


@app.get("/models/{model_id}/earnings")
async def get_model_earnings(
    model_id: str, limit: int = 20, session=Depends(get_session)
):
    entries = await repo.list_model_earnings(session, model_id, limit=limit)
    return [
        {
            "ts": e.created_at.isoformat(),
            "agent_id": e.agent_id,
            "amount": float(e.amount) if e.amount is not None else 0.0,
            "judge_score": None,
        }
        for e in entries
    ]


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


@app.post("/auth/register", response_model=AuthResponse)
async def auth_register(body: RegisterBody, session=Depends(get_session)):
    email = body.email.strip().lower()
    if not email or not body.password:
        raise HTTPException(status_code=400, detail="email and password required")
    if await repo.get_user_by_email(session, email) is not None:
        raise HTTPException(status_code=409, detail="email already registered")
    name = (body.name or email.split("@")[0]).strip() or email.split("@")[0]
    u = await repo.create_user(
        session,
        email=email,
        name=name,
        credits=USER_START_CREDITS,
        password_hash=hash_password(body.password),
    )
    await session.commit()
    return AuthResponse(
        user_id=str(u.id), name=u.name, email=u.email, credits=float(u.credits)
    )


@app.post("/auth/login", response_model=AuthResponse)
async def auth_login(body: LoginBody, session=Depends(get_session)):
    email = body.email.strip().lower()
    user = await repo.get_user_by_email(session, email)
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid email or password")
    return AuthResponse(
        user_id=str(user.id),
        name=user.name,
        email=user.email,
        credits=float(user.credits),
    )


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
