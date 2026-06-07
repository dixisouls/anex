"""
Apply a realistic mid-session market snapshot on top of a fresh seed.

Varied model price trends (some up, some down), agent reps/hires/wins,
sim investor holdings, synthetic trade history, completed tasks in Postgres,
and matching feed events so Exchange + Network show lived-in state after refresh.

Prerequisites: run reset_fresh first.

    WEAVE_DISABLED=1 EMBEDDINGS_FAKE=1 python -m backend.tools.market_snapshot

Or: ./scripts/seed_market_snapshot.sh
"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta, timezone

from contracts.events import (
    AgentHired,
    CandidatesRanked,
    PortfolioChanged,
    PriceChanged,
    TaskExecuted,
    TaskPosted,
    TaskScored,
)
from contracts.schemas import Candidate, Subtask
from backend.config import MARKET_SESSION_KEY, TIER_IPO_PRICE
from backend.db import repo
from backend.infra.db import session_scope
from backend.infra.redis_client import close_redis, get_redis
from backend.market import dynamics, feed, registry, trading
from backend.market.seed_agents import SEED_AGENTS
from backend.market.seed_models import SEED_MODELS

# Price multiplier vs IPO ( >1 = up, <1 = down ) — hand-tuned board shape.
MODEL_DRIFT: dict[str, float] = {
    "gemini-3.5-flash": 1.24,
    "gpt-5.5": 1.18,
    "xai/grok-4.20-reasoning": 1.12,
    "zai-org/glm-5-maas": 1.08,
    "gemini-3.1-pro-preview": 0.96,
    "meta/llama-4-maverick-17b-128e-instruct-maas": 0.94,
    "gpt-5.4-mini": 0.91,
    "xai/grok-4.1-fast-non-reasoning": 0.88,
    "gemini-3.1-flash-lite": 0.85,
    "gpt-4.1-mini": 0.83,
    "xai/grok-4.20-non-reasoning": 0.80,
    "gpt-4.1": 0.76,
    "gemma-4-26b-a4b-it-maas": 0.72,
    "xai/grok-4.1-fast-reasoning": 0.70,
}

HISTORY_GOALS: list[tuple[str, list[str]]] = [
    (
        "What is the current state of Redis?",
        [
            "Survey recent Redis releases, cluster features, and enterprise adoption.",
            "Write an executive summary of Redis positioning vs alternatives.",
        ],
    ),
    (
        "Do market research on the current state of gaming consoles.",
        [
            "Compile sales and attach-rate data for PS5, Xbox Series, and Switch.",
            "Perform a SWOT analysis for each major console platform.",
            "Synthesize findings into a one-page investor brief.",
        ],
    ),
    (
        "Draft a launch email for a developer tools SaaS product.",
        [
            "Research comparable dev-tool launches and messaging angles.",
            "Write the launch email with subject line variants.",
        ],
    ),
]


def _iso(minutes_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()


async def _backfill_price_path(
    r,
    session,
    *,
    model_id: str,
    tier: str,
    ipo: float,
    target: float,
    rng: random.Random,
    ticks: int = 120,
) -> None:
    m = await repo.get_model(session, model_id)
    if m is None:
        return
    shares = float(m.pool_shares)
    prices = dynamics.generate_gbm_path(ipo, target, steps=ticks, tier=tier, rng=rng)
    for p in prices:
        await registry.append_price_tick(
            r, model_id=model_id, price=round(p, 4), reason="snapshot"
        )
    await repo.update_model_pool(session, model_id, shares=shares, credits=shares * target)
    await registry.init_market_fields(r, model_id, ipo)
    await r.hset(
        registry.model_key(model_id),
        mapping={
            "fundamental": str(target),
            "session_open": str(ipo),
            "day_high": str(max(prices)),
            "day_low": str(min(prices)),
            "volume_24h": str(rng.uniform(50, 400)),
        },
    )
    await r.hset(MARKET_SESSION_KEY, model_id, str(ipo))
    m = await repo.get_model(session, model_id)
    await registry.project_model(r, m)


async def _shape_agents(r, session, rng: random.Random) -> None:
    by_cap: dict[str, list] = {}
    for a in await repo.list_agents(session):
        by_cap.setdefault(a.capability_id, []).append(a)

    for siblings in by_cap.values():
        siblings.sort(key=lambda a: a.service_tier, reverse=True)
        for rank, agent in enumerate(siblings):
            if rank == 0:
                rep = rng.uniform(0.72, 0.92)
                hires = rng.randint(12, 45)
            elif rank == 1:
                rep = rng.uniform(0.55, 0.74)
                hires = rng.randint(5, 20)
            else:
                rep = rng.uniform(0.38, 0.58)
                hires = rng.randint(1, 10)
            wins = max(0, int(hires * rng.uniform(0.45, 0.85)))
            treasury = 100.0 + hires * rng.uniform(8, 35)
            await repo.update_agent_stats(
                session,
                agent.agent_id,
                reputation=rep,
                credits=treasury,
                inc_hires=hires,
                inc_wins=wins,
            )
            await registry.reproject_agent(r, session, agent.agent_id)


async def _sim_trades(r, session, rng: random.Random) -> None:
    users = [u for u in await repo.list_users(session) if u.is_sim and "investor" in u.email]
    models = await repo.list_models(session)
    if not users or not models:
        return

    hot = {mid for mid, d in MODEL_DRIFT.items() if d >= 1.05}
    cold = {mid for mid, d in MODEL_DRIFT.items() if d < 0.9}

    for user in users[:6]:
        uid = user.id
        picks = rng.sample([m.model_id for m in models], k=min(4, len(models)))
        for mid in picks:
            try:
                if mid in hot or rng.random() > 0.35:
                    amount = rng.uniform(25, min(90, float(user.credits) * 0.15))
                    await trading.trade(
                        session, r, user_id=uid, model_id=mid, side="buy", amount=amount
                    )
                elif mid in cold and rng.random() > 0.5:
                    h = await repo.get_holding(session, uid, mid)
                    if h and float(h.shares) > 1:
                        await trading.trade(
                            session,
                            r,
                            user_id=uid,
                            model_id=mid,
                            side="sell",
                            amount=min(float(h.shares) * 0.4, 50),
                        )
            except (ValueError, KeyError):
                continue


async def _synthetic_tasks(r, session, rng: random.Random) -> None:
    posters = [u for u in await repo.list_users(session) if u.is_sim and "poster" in u.email]
    if not posters:
        return

    agents_by_cap = {}
    for a in SEED_AGENTS:
        agents_by_cap.setdefault(a.capability_id, []).append(a)

    minute = 900
    for goal, step_texts in HISTORY_GOALS:
        poster = rng.choice(posters)
        task = await repo.create_task(session, goal=goal, user_id=poster.id)
        task_id = str(task.id)
        task_uuid = task.id

        subtasks: list[Subtask] = []
        for i, text in enumerate(step_texts):
            await repo.create_subtask(session, task_id=task_uuid, order_index=i, text=text)
            subtasks.append(Subtask(subtask_id=f"{task_id}-{i}", text=text))

        await feed.emit(
            r,
            TaskPosted(
                task_id=task_id,
                goal=goal,
                subtasks=subtasks,
                broker_model="gemini-3.5-flash",
                preferred_tier="flash",
                ts=_iso(minute),
            ),
        )
        minute -= 45

        budget_left = rng.uniform(180, 420)
        for i, st in enumerate(subtasks):
            cap_agents = list(SEED_AGENTS)
            agent = rng.choice(cap_agents)
            price = rng.uniform(35, 75)
            score = rng.uniform(0.55, 0.88)
            budget_left = max(0, budget_left - price)

            cand = Candidate(
                agent_id=agent.agent_id,
                match_score=rng.uniform(0.7, 0.95),
                reputation=agent.reputation,
                price=price,
                final_score=rng.uniform(0.6, 0.9),
            )
            await feed.emit(
                r,
                CandidatesRanked(
                    subtask_id=st.subtask_id,
                    candidates=[cand],
                    ts=_iso(minute - 2),
                ),
            )
            await feed.emit(
                r,
                AgentHired(
                    subtask_id=st.subtask_id,
                    agent_id=agent.agent_id,
                    price=price,
                    budget_remaining=budget_left,
                    ts=_iso(minute - 1),
                ),
            )
            preview = (
                f"Completed output for step {i + 1}: {st.text[:120]}… "
                f"(synthetic snapshot)"
            )
            await feed.emit(
                r,
                TaskExecuted(
                    subtask_id=st.subtask_id,
                    agent_id=agent.agent_id,
                    output_preview=preview,
                    ts=_iso(minute),
                ),
            )
            await feed.emit(
                r,
                TaskScored(
                    subtask_id=st.subtask_id,
                    agent_id=agent.agent_id,
                    judge_score=score,
                    ts=_iso(minute + 1),
                ),
            )
            await repo.save_subtask_result(
                session,
                subtask_id=st.subtask_id,
                agent_id=agent.agent_id,
                output_preview=preview,
                judge_score=score,
            )
            minute -= 20


async def apply_snapshot() -> None:
    r = get_redis()
    rng = random.Random(42)

    async with session_scope() as session:
        models = await repo.list_models(session)
        if not models:
            raise SystemExit("No models in DB — run reset_fresh.sh first.")

        for spec in SEED_MODELS:
            mid = spec["model_id"]
            tier = spec["tier"]
            ipo = TIER_IPO_PRICE[tier]
            drift = MODEL_DRIFT.get(mid, rng.uniform(0.85, 1.15))
            target = round(ipo * drift, 4)
            await _backfill_price_path(
                r,
                session,
                model_id=mid,
                tier=tier,
                ipo=ipo,
                target=target,
                rng=rng,
            )
            old = ipo
            await feed.emit(
                r,
                PriceChanged(
                    model_id=mid,
                    old=old,
                    new=target,
                    reason="snapshot",
                    ts=_iso(rng.randint(5, 60)),
                ),
            )

        await _shape_agents(r, session, rng)
        await _sim_trades(r, session, rng)
        await _synthetic_tasks(r, session, rng)

        for user in await repo.list_users(session):
            if not user.is_sim:
                continue
            from backend.market import portfolio as portfolio_mod

            p = await portfolio_mod.value(session, r, user.id)
            await feed.emit(
                r,
                PortfolioChanged(
                    user_id=str(user.id),
                    credits=p.credits,
                    holdings_value=p.holdings_value,
                    total=p.total,
                    ts=_iso(1),
                ),
            )


async def _main() -> None:
    await apply_snapshot()
    print("Market snapshot applied.")
    print("  - Model charts: mixed up/down trends with price history")
    print("  - Agents: varied reputation, hires, wins, treasury")
    print("  - Sim investors: sample holdings + trades")
    print("  - Feed: 3 completed task threads (refresh the app to load)")
    print()
    print("Restart or hard-refresh the frontend, then log in as a new guest.")
    await close_redis()


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
