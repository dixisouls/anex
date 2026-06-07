"""
Offline ledger settle tests.

    EMBEDDINGS_FAKE=1 WEAVE_DISABLED=1 pytest tests/0005_ledger.py -v
"""

from unittest.mock import AsyncMock, patch

import pytest

from contracts.schemas import Agent
from backend.config import REP_ALPHA
from backend.market import ledger


@pytest.mark.asyncio
async def test_settle_reputation_ema_high_score():
    old_rep = 0.5
    score = 1.0
    expected_rep = REP_ALPHA * score + (1 - REP_ALPHA) * old_rep
    agent = Agent(
        agent_id="writer-flash",
        capability_id="writer",
        service_tier="flash",
        name="Copywriter",
        skills=["writing"],
        capability_text="writes copy",
        model="gemini-3.5-flash",
        reputation=old_rep,
        credits=100.0,
        margin=0.2,
    )
    session = AsyncMock()
    r = AsyncMock()
    captured: dict = {}

    async def capture_stats(_session, agent_id, *, reputation, credits, inc_hires, inc_wins):
        captured.update(
            reputation=reputation,
            credits=credits,
            inc_hires=inc_hires,
            inc_wins=inc_wins,
        )

    with (
        patch.object(ledger.repo, "get_agent", new_callable=AsyncMock, return_value=agent),
        patch.object(ledger.repo, "update_agent_stats", side_effect=capture_stats),
        patch.object(ledger.repo, "add_ledger_entry", new_callable=AsyncMock),
        patch.object(ledger.registry, "update_leaderboard", new_callable=AsyncMock),
        patch.object(ledger.registry, "reproject_agent", new_callable=AsyncMock),
        patch.object(ledger.repo, "get_model", new_callable=AsyncMock, return_value=None),
        patch.object(ledger.exchange, "inject_earnings", new_callable=AsyncMock),
        patch.object(ledger.bus, "publish", new_callable=AsyncMock),
    ):
        await ledger.settle(
            r,
            session,
            agent_id="writer-flash",
            model_id="gemini-3.5-flash",
            judge_score=score,
            derived_price=24.0,
            task_id="00000000-0000-0000-0000-000000000001",
        )

    assert captured["reputation"] == pytest.approx(expected_rep)
    assert captured["inc_hires"] == 1
    assert captured["inc_wins"] == 1


@pytest.mark.asyncio
async def test_settle_reputation_ema_low_score():
    old_rep = 0.5
    score = 0.0
    expected_rep = REP_ALPHA * score + (1 - REP_ALPHA) * old_rep
    agent = Agent(
        agent_id="writer-flash",
        capability_id="writer",
        service_tier="flash",
        name="Copywriter",
        skills=["writing"],
        capability_text="writes copy",
        model="gemini-3.5-flash",
        reputation=old_rep,
        credits=100.0,
        margin=0.2,
    )
    session = AsyncMock()
    r = AsyncMock()
    captured: dict = {}

    async def capture_stats(_session, agent_id, *, reputation, credits, inc_hires, inc_wins):
        captured.update(reputation=reputation, inc_wins=inc_wins)

    with (
        patch.object(ledger.repo, "get_agent", new_callable=AsyncMock, return_value=agent),
        patch.object(ledger.repo, "update_agent_stats", side_effect=capture_stats),
        patch.object(ledger.repo, "add_ledger_entry", new_callable=AsyncMock),
        patch.object(ledger.registry, "update_leaderboard", new_callable=AsyncMock),
        patch.object(ledger.registry, "reproject_agent", new_callable=AsyncMock),
        patch.object(ledger.repo, "get_model", new_callable=AsyncMock, return_value=None),
        patch.object(ledger.exchange, "inject_earnings", new_callable=AsyncMock),
        patch.object(ledger.bus, "publish", new_callable=AsyncMock),
    ):
        await ledger.settle(
            r,
            session,
            agent_id="writer-flash",
            model_id="gemini-3.5-flash",
            judge_score=score,
            derived_price=24.0,
            task_id="00000000-0000-0000-0000-000000000001",
        )

    assert captured["reputation"] == pytest.approx(expected_rep)
    assert captured["inc_wins"] == 0
