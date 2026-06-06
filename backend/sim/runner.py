"""Controllable async sim loops calling the public API over HTTP."""

from __future__ import annotations

import asyncio
import json
import logging
import random

import httpx
import weave

from backend.config import (
    API_URL,
    OPENAI_CHAT_MODEL,
    SIM_CADENCE_S,
    SIM_INVESTORS,
    SIM_POSTERS,
    TRADE_CAP,
)

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


def parse_investor_response(raw: str, valid_model_ids: set[str]) -> dict:
    """Parse constrained investor JSON; default to hold on failure."""
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start < 0 or end <= start:
            return {"action": "hold"}
        data = json.loads(raw[start:end])
        if data.get("action") == "hold":
            return {"action": "hold"}
        model_id = data.get("model_id")
        side = data.get("side")
        amount = float(data.get("amount", 0))
        if model_id not in valid_model_ids or side not in ("buy", "sell") or amount <= 0:
            return {"action": "hold"}
        return {"model_id": model_id, "side": side, "amount": amount}
    except Exception:
        return {"action": "hold"}


@weave.op
def investor_decision(market_snapshot: dict, portfolio: dict) -> dict:
    """OpenAI: decide {model_id, side, amount} or {action: hold}."""
    model_ids = [m["model_id"] for m in market_snapshot.get("models", [])]
    prompt = (
        "You are a model-stock investor. Given MARKET and PORTFOLIO, decide one trade or hold.\n"
        "Reply ONLY JSON, exactly one of:\n"
        '  {"action":"hold"}\n'
        '  {"model_id":"<id>","side":"buy"|"sell","amount":<positive number>}\n'
        "Keep amount modest (under 100 credits/shares).\n"
        f"Valid model_ids: {model_ids}\n"
        f"Available credits: {portfolio.get('credits', 0)}\n\n"
        f"MARKET:\n{json.dumps(market_snapshot)[:4000]}\n\n"
        f"PORTFOLIO:\n{json.dumps(portfolio)[:2000]}\n"
    )
    try:
        from openai import OpenAI

        raw = OpenAI().responses.create(model=OPENAI_CHAT_MODEL, input=prompt).output_text
        return parse_investor_response(raw.strip(), set(model_ids))
    except Exception:
        logger.exception("investor_decision failed; holding")
        return {"action": "hold"}


def trade_from_decision(decision: dict, *, trade_cap: float = TRADE_CAP) -> dict | None:
    """Build a /trade body from a decision, capping size. None means hold."""
    if decision.get("action") == "hold":
        return None
    return {
        "model_id": decision["model_id"],
        "side": decision["side"],
        "amount": min(float(decision["amount"]), trade_cap),
    }


async def _ensure_sim_users(
    client: httpx.AsyncClient, n_posters: int, n_investors: int
) -> tuple[list[str], list[str]]:
    resp = await client.get("/users")
    resp.raise_for_status()
    sim_users = [u for u in resp.json() if u.get("is_sim")]

    posters = [u["user_id"] for u in sim_users if u.get("name", "").startswith("sim-poster")]
    investors = [
        u["user_id"] for u in sim_users if u.get("name", "").startswith("sim-investor")
    ]

    while len(posters) < n_posters:
        i = len(posters) + 1
        r = await client.post(
            "/users",
            json={"name": f"sim-poster-{i}", "email": f"sim-poster-{i}@bazaar.local", "is_sim": True},
        )
        r.raise_for_status()
        posters.append(r.json()["user_id"])

    while len(investors) < n_investors:
        i = len(investors) + 1
        r = await client.post(
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
                await client.post("/task", json={"goal": gen_goal(), "user_id": user_id})
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("poster loop error user=%s", user_id)
            await asyncio.sleep(cadence_s)


async def _investor_loop(base_url: str, user_id: str, cadence_s: float) -> None:
    async with httpx.AsyncClient(base_url=base_url, timeout=120) as client:
        while True:
            try:
                market = (await client.get("/market")).json()
                pf = (await client.get(f"/portfolio/{user_id}")).json()
                decision = investor_decision(market, pf)
                trade = trade_from_decision(decision)
                if trade is not None:
                    trade["user_id"] = user_id
                    await client.post("/trade", json=trade)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("investor loop error user=%s", user_id)
            await asyncio.sleep(cadence_s)


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
    for uid in investor_ids:
        _tasks.append(asyncio.create_task(_investor_loop(base_url, uid, cadence_s)))


async def stop() -> None:
    """Cancel all running sim loops."""
    global _tasks
    pending = _tasks
    _tasks = []
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
