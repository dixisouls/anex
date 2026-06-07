"""Controllable async sim loops calling the public API over HTTP."""

from __future__ import annotations

import asyncio
import logging
import random

import httpx
import weave

from backend.config import (
    API_URL,
    OPENAI_CHAT_MODEL,
    SIM_CADENCE_JITTER,
    SIM_CADENCE_S,
    SIM_INVESTORS,
    SIM_POSTERS,
    TRADE_CAP,
)
from backend.infra.retry import httpx_request_with_retry
from backend.sim import strategies

logger = logging.getLogger(__name__)

_tasks: list[asyncio.Task] = []

_FALLBACK_GOALS = (
    "Draft a short README for a Python CLI that converts CSV to Parquet.",
    "Summarize the tradeoffs between Redis streams and Pub/Sub for event feeds.",
    "Write a unit test plan for a constant-product AMM exchange.",
    "Research three approaches to embedding-based agent matching and compare them.",
)


@weave.op
def gen_goal() -> str:
    """OpenAI: produce one realistic, varied work goal (one line)."""
    try:
        from openai import OpenAI

        text = (
            OpenAI()
            .responses.create(
                model=OPENAI_CHAT_MODEL,
                input=(
                    "Invent ONE realistic short work request "
                    "(writing/coding/research). One line only."
                ),
            )
            .output_text.strip()
        )
        return text or random.choice(_FALLBACK_GOALS)
    except Exception:
        logger.exception("gen_goal failed; using fallback")
        return random.choice(_FALLBACK_GOALS)


def trade_from_decision(decision: dict, *, trade_cap: float = TRADE_CAP) -> dict | None:
    """Build a /trade body from a decision, capping size. None means hold."""
    if decision.get("action") == "hold":
        return None
    return {
        "model_id": decision["model_id"],
        "side": decision["side"],
        "amount": min(float(decision["amount"]), trade_cap),
    }


async def _api_get(client: httpx.AsyncClient, path: str):
    return await httpx_request_with_retry(lambda: client.get(path))


async def _api_post(client: httpx.AsyncClient, path: str, *, json: dict | None = None):
    return await httpx_request_with_retry(lambda: client.post(path, json=json))


async def _wait_for_task_slot(client: httpx.AsyncClient, poll_s: float = 1.0) -> None:
    """Block until the API reports a free broker pipeline slot."""
    while True:
        resp = await _api_get(client, "/task/slots")
        resp.raise_for_status()
        if resp.json().get("available", 0) > 0:
            return
        await asyncio.sleep(poll_s)


async def _ensure_sim_users(
    client: httpx.AsyncClient, n_posters: int, n_investors: int
) -> tuple[list[str], list[str]]:
    resp = await _api_get(client, "/users")
    resp.raise_for_status()
    sim_users = [u for u in resp.json() if u.get("is_sim")]

    posters = [u["user_id"] for u in sim_users if u.get("name", "").startswith("sim-poster")]
    investors = [
        u["user_id"] for u in sim_users if u.get("name", "").startswith("sim-investor")
    ]

    while len(posters) < n_posters:
        i = len(posters) + 1
        r = await _api_post(
            client,
            "/users",
            json={"name": f"sim-poster-{i}", "email": f"sim-poster-{i}@bazaar.local", "is_sim": True},
        )
        r.raise_for_status()
        posters.append(r.json()["user_id"])

    while len(investors) < n_investors:
        i = len(investors) + 1
        r = await _api_post(
            client,
            "/users",
            json={
                "name": f"sim-investor-{i}",
                "email": f"sim-investor-{i}@bazaar.local",
                "is_sim": True,
            },
        )
        r.raise_for_status()
        investors.append(r.json()["user_id"])

    return posters[:n_posters], investors[:n_investors]


async def _poster_loop(base_url: str, user_id: str, cadence_s: float) -> None:
    async with httpx.AsyncClient(base_url=base_url, timeout=120) as client:
        while True:
            try:
                await _wait_for_task_slot(client)
                goal = await asyncio.to_thread(gen_goal)
                await _api_post(client, "/task", json={"goal": goal, "user_id": user_id})
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("poster loop error user=%s", user_id)
            await asyncio.sleep(cadence_s)


def _jittered(cadence_s: float, rng: random.Random) -> float:
    """Cadence with +/- SIM_CADENCE_JITTER fraction so investors desync."""
    span = cadence_s * SIM_CADENCE_JITTER
    return max(0.1, cadence_s + rng.uniform(-span, span))


async def _investor_loop(
    base_url: str,
    user_id: str,
    cadence_s: float,
    strategy: str = strategies.NOISE,
    rng: random.Random | None = None,
) -> None:
    rng = rng or random.Random(user_id)
    async with httpx.AsyncClient(base_url=base_url, timeout=120) as client:
        while True:
            try:
                market = (await _api_get(client, "/market")).json()
                pf = (await _api_get(client, f"/portfolio/{user_id}")).json()
                decision = strategies.decide(
                    strategy, market, pf, rng, trade_cap=TRADE_CAP
                )
                trade = trade_from_decision(decision)
                if trade is not None:
                    trade["user_id"] = user_id
                    await _api_post(client, "/trade", json=trade)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("investor loop error user=%s", user_id)
            await asyncio.sleep(_jittered(cadence_s, rng))


async def start(
    base_url: str = API_URL,
    *,
    n_posters: int | None = None,
    n_investors: int | None = None,
    cadence_s: float | None = None,
) -> None:
    """Spawn poster and investor loops; track tasks for stop()."""
    await stop()
    n_posters = SIM_POSTERS if n_posters is None else n_posters
    n_investors = SIM_INVESTORS if n_investors is None else n_investors
    cadence_s = SIM_CADENCE_S if cadence_s is None else cadence_s

    async with httpx.AsyncClient(base_url=base_url, timeout=120) as client:
        poster_ids, investor_ids = await _ensure_sim_users(client, n_posters, n_investors)

    for uid in poster_ids:
        _tasks.append(asyncio.create_task(_poster_loop(base_url, uid, cadence_s)))
    for i, uid in enumerate(investor_ids):
        strategy = strategies.STRATEGIES[i % len(strategies.STRATEGIES)]
        rng = random.Random(f"{uid}:{strategy}")
        logger.info("investor %s -> strategy=%s", uid, strategy)
        _tasks.append(
            asyncio.create_task(
                _investor_loop(base_url, uid, cadence_s, strategy, rng)
            )
        )


async def stop() -> None:
    """Cancel all running sim loops."""
    global _tasks
    pending = _tasks
    _tasks = []
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
