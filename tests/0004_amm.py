"""
Offline AMM unit tests (no live DB).

    EMBEDDINGS_FAKE=1 WEAVE_DISABLED=1 pytest tests/0004_amm.py -v
"""

from unittest.mock import AsyncMock, patch

import pytest

from backend.db.models import Model as ModelORM
from backend.market import exchange


def _flash_model() -> ModelORM:
    return ModelORM(
        model_id="gemini-3.5-flash",
        name="Gemini 3.5 Flash",
        provider="gcp",
        tier="flash",
        executable=True,
        pool_shares=1000.0,
        pool_credits=20000.0,
        ipo_price=20.0,
    )


@pytest.fixture
def pool_state():
    model = _flash_model()
    state = {"shares": 1000.0, "credits": 20000.0}

    async def get_model(_session, model_id):
        model.pool_shares = state["shares"]
        model.pool_credits = state["credits"]
        return model

    async def update_pool(_session, model_id, *, shares, credits):
        state["shares"] = shares
        state["credits"] = credits
        model.pool_shares = shares
        model.pool_credits = credits

    return model, state, get_model, update_pool


@pytest.mark.asyncio
async def test_buy_raises_price_preserves_k(pool_state):
    model, state, get_model, update_pool = pool_state
    session = AsyncMock()
    r = AsyncMock()
    S, C = state["shares"], state["credits"]
    k = S * C
    old_price = C / S

    with (
        patch.object(exchange.repo, "get_model", side_effect=get_model),
        patch.object(exchange.repo, "update_model_pool", side_effect=update_pool),
        patch.object(exchange.registry, "project_model", new_callable=AsyncMock),
        patch.object(exchange.registry, "bump_session_stats", new_callable=AsyncMock),
        patch.object(exchange.registry, "append_price_tick", new_callable=AsyncMock),
        patch.object(exchange.bus, "publish", new_callable=AsyncMock),
    ):
        shares_out, new_price = await exchange.buy(
            session, r, model_id=model.model_id, dc=1000.0
        )

    assert shares_out > 0
    assert new_price > old_price
    assert abs(state["shares"] * state["credits"] - k) < 1e-6


@pytest.mark.asyncio
async def test_inject_earnings_raises_price_unchanged_shares(pool_state):
    model, state, get_model, update_pool = pool_state
    session = AsyncMock()
    r = AsyncMock()
    old_shares = state["shares"]
    old_price = state["credits"] / state["shares"]

    with (
        patch.object(exchange.repo, "get_model", side_effect=get_model),
        patch.object(exchange.repo, "update_model_pool", side_effect=update_pool),
        patch.object(exchange.registry, "project_model", new_callable=AsyncMock),
        patch.object(exchange.registry, "bump_session_stats", new_callable=AsyncMock),
        patch.object(exchange.registry, "append_price_tick", new_callable=AsyncMock),
        patch.object(exchange.bus, "publish", new_callable=AsyncMock),
    ):
        await exchange.inject_earnings(
            session,
            r,
            model_id=model.model_id,
            agent_id="writer-01",
            amount=50.0,
            judge_score=0.8,
        )

    new_price = state["credits"] / state["shares"]
    assert state["shares"] == old_shares
    assert new_price > old_price


@pytest.mark.asyncio
async def test_buy_rejects_too_small_trade(pool_state):
    _, state, get_model, update_pool = pool_state
    session = AsyncMock()
    r = AsyncMock()

    with (
        patch.object(exchange.repo, "get_model", side_effect=get_model),
        patch.object(exchange.repo, "update_model_pool", side_effect=update_pool),
        patch.object(exchange.registry, "project_model", new_callable=AsyncMock),
        patch.object(exchange.bus, "publish", new_callable=AsyncMock),
    ):
        with pytest.raises(ValueError, match="trade too small"):
            await exchange.buy(session, r, model_id="gemini-3.5-flash", dc=1e-12)
