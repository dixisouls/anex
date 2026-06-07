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
    POSTER_BUDGET_CAP,
    SIM_CADENCE_JITTER,
    SIM_CADENCE_S,
    SIM_INVESTOR_MODE,
    SIM_INVESTORS,
    SIM_POSTERS,
    TRADE_CAP,
)
from backend.infra.retry import httpx_request_with_retry
from backend.sim import cohorts, llm_investor, strategies

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
                pf = (await _api_get(client, f"/portfolio/{user_id}")).json()
                budget = min(float(pf.get("credits", 0)), POSTER_BUDGET_CAP)
                if budget < 5:
                    await asyncio.sleep(cadence_s)
                    continue
                await _api_post(
                    client,
                    "/task",
                    json={"goal": goal, "user_id": user_id, "budget": budget},
                )
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
    *,
    mode: str = "math",
    strategy: str = strategies.NOISE,
    trade_cap: float = TRADE_CAP,
    start_delay_s: float = 0.0,
    cohort: str = "legacy",
    rng: random.Random | None = None,
) -> None:
    rng = rng or random.Random(user_id)
    if start_delay_s > 0:
        await asyncio.sleep(start_delay_s)
    async with httpx.AsyncClient(base_url=base_url, timeout=120) as client:
        while True:
            try:
                market = (await _api_get(client, "/market")).json()
                pf = (await _api_get(client, f"/portfolio/{user_id}")).json()
                if mode == "math":
                    decision = strategies.decide(
                        strategy, market, pf, rng, trade_cap=trade_cap
                    )
                else:
                    snapshot = llm_investor.build_snapshot(market, pf, rng=rng)
                    snapshot = await llm_investor.enrich_snapshot(client, snapshot)
                    raw = await asyncio.to_thread(
                        llm_investor.llm_decide, strategy, snapshot, rng=rng
                    )
                    decision = llm_investor.validate_decision(
                        raw, market, pf, trade_cap=trade_cap
                    )
                trade = trade_from_decision(decision, trade_cap=trade_cap)
                if trade is not None:
                    trade["user_id"] = user_id
                    await _api_post(client, "/trade", json=trade)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "investor loop error user=%s cohort=%s", user_id, cohort
                )
            await asyncio.sleep(_jittered(cadence_s, rng))


def _spawn_legacy_investors(
    base_url: str,
    investor_ids: list[str],
    cadence_s: float,
) -> None:
    for i, uid in enumerate(investor_ids):
        strategy = strategies.STRATEGIES[i % len(strategies.STRATEGIES)]
        mode = SIM_INVESTOR_MODE if SIM_INVESTOR_MODE in ("math", "llm") else "llm"
        rng = random.Random(f"{uid}:{strategy}")
        logger.info(
            "investor %s -> cohort=legacy mode=%s strategy=%s cadence_s=%s",
            uid,
            mode,
            strategy,
            cadence_s,
        )
        _tasks.append(
            asyncio.create_task(
                _investor_loop(
                    base_url,
                    uid,
                    cadence_s,
                    mode=mode,
                    strategy=strategy,
                    cohort="legacy",
                    rng=rng,
                )
            )
        )


def _spawn_cohort_investors(
    base_url: str,
    investor_ids: list[str],
    assignments: list[cohorts.InvestorAssignment],
) -> None:
    for uid, spec in zip(investor_ids, assignments):
        rng = random.Random(f"{uid}:{spec.cohort}:{spec.strategy}")
        logger.info(
            "investor %s -> cohort=%s mode=%s strategy=%s cadence_s=%s trade_cap=%s",
            uid,
            spec.cohort,
            spec.mode,
            spec.strategy,
            spec.cadence_s,
            spec.trade_cap,
        )
        _tasks.append(
            asyncio.create_task(
                _investor_loop(
                    base_url,
                    uid,
                    spec.cadence_s,
                    mode=spec.mode,
                    strategy=spec.strategy,
                    trade_cap=spec.trade_cap,
                    start_delay_s=spec.start_delay_s,
                    cohort=spec.cohort,
                    rng=rng,
                )
            )
        )


async def start(
    base_url: str = API_URL,
    *,
    n_posters: int | None = None,
    n_investors: int | None = None,
    cadence_s: float | None = None,
    use_cohorts: bool | None = None,
) -> None:
    """Spawn poster and investor loops; track tasks for stop()."""
    await stop()
    n_posters = SIM_POSTERS if n_posters is None else n_posters
    cadence_s = SIM_CADENCE_S if cadence_s is None else cadence_s
    cohort_mode = cohorts.cohorts_enabled() if use_cohorts is None else use_cohorts

    if cohort_mode:
        cohort_list = cohorts.default_cohorts()
        assignments = cohorts.expand_assignments(cohort_list)
        n_investors = len(assignments)
        logger.info(
            "sim cohorts enabled: %s investors (%s math, %s llm)",
            n_investors,
            sum(1 for a in assignments if a.mode == "math"),
            sum(1 for a in assignments if a.mode == "llm"),
        )
    else:
        n_investors = SIM_INVESTORS if n_investors is None else n_investors
        assignments = []

    async with httpx.AsyncClient(base_url=base_url, timeout=120) as client:
        poster_ids, investor_ids = await _ensure_sim_users(client, n_posters, n_investors)

    for uid in poster_ids:
        _tasks.append(asyncio.create_task(_poster_loop(base_url, uid, cadence_s)))

    if cohort_mode:
        _spawn_cohort_investors(base_url, investor_ids, assignments)
    else:
        _spawn_legacy_investors(base_url, investor_ids, cadence_s)


async def stop() -> None:
    """Cancel all running sim loops."""
    global _tasks
    pending = _tasks
    _tasks = []
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
