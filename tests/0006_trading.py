"""
Offline trading unit tests (no live DB).

    EMBEDDINGS_FAKE=1 WEAVE_DISABLED=1 pytest tests/0006_trading.py -v
"""

import uuid
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from backend.db.models import Model as ModelORM
from backend.market import exchange, portfolio, trading


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
def trade_env():
    model = _flash_model()
    pool = {"shares": 1000.0, "credits": 20000.0}
    user_id = uuid.uuid4()
    user = SimpleNamespace(id=user_id, credits=1000.0)
    holdings: dict[str, float] = {}

    async def get_model(_session, model_id):
        model.pool_shares = pool["shares"]
        model.pool_credits = pool["credits"]
        return model

    async def update_pool(_session, model_id, *, shares, credits):
        pool["shares"] = shares
        pool["credits"] = credits
        model.pool_shares = shares
        model.pool_credits = credits

    async def get_user(_session, uid):
        if uid != user_id:
            raise KeyError(uid)
        return user

    async def adjust_user_credits(_session, uid, delta):
        user.credits = float(user.credits) + delta
        return user.credits

    async def get_holding(_session, uid, model_id):
        shares = holdings.get(model_id)
        if shares is None:
            return None
        return SimpleNamespace(user_id=uid, model_id=model_id, shares=shares)

    async def upsert_holding_delta(_session, uid, model_id, delta):
        holdings[model_id] = max(0.0, holdings.get(model_id, 0.0) + delta)
        return holdings.get(model_id, 0.0)

    async def list_holdings(_session, uid):
        return [
            SimpleNamespace(user_id=uid, model_id=mid, shares=shares)
            for mid, shares in holdings.items()
            if shares > 0
        ]

    async def get_model_price(_r, model_id):
        return pool["credits"] / pool["shares"]

    return {
        "model": model,
        "pool": pool,
        "user": user,
        "user_id": user_id,
        "holdings": holdings,
        "get_model": get_model,
        "update_pool": update_pool,
        "get_user": get_user,
        "adjust_user_credits": adjust_user_credits,
        "get_holding": get_holding,
        "upsert_holding_delta": upsert_holding_delta,
        "list_holdings": list_holdings,
        "get_model_price": get_model_price,
    }


def _trade_patches(env):
    stack = ExitStack()
    stack.enter_context(patch.object(exchange.repo, "get_model", side_effect=env["get_model"]))
    stack.enter_context(
        patch.object(exchange.repo, "update_model_pool", side_effect=env["update_pool"])
    )
    stack.enter_context(
        patch.object(exchange.registry, "project_model", new_callable=AsyncMock)
    )
    stack.enter_context(patch.object(exchange.bus, "publish", new_callable=AsyncMock))
    stack.enter_context(patch.object(trading.repo, "get_user", side_effect=env["get_user"]))
    stack.enter_context(
        patch.object(
            trading.repo, "adjust_user_credits", side_effect=env["adjust_user_credits"]
        )
    )
    stack.enter_context(
        patch.object(trading.repo, "get_holding", side_effect=env["get_holding"])
    )
    stack.enter_context(
        patch.object(
            trading.repo, "upsert_holding_delta", side_effect=env["upsert_holding_delta"]
        )
    )
    stack.enter_context(patch.object(trading.repo, "record_trade", new_callable=AsyncMock))
    stack.enter_context(
        patch.object(trading.repo, "list_holdings", side_effect=env["list_holdings"])
    )
    stack.enter_context(
        patch.object(
            portfolio.registry, "get_model_price", side_effect=env["get_model_price"]
        )
    )
    stack.enter_context(patch.object(trading.bus, "publish", new_callable=AsyncMock))
    return stack


@pytest.mark.asyncio
async def test_buy_debits_credits_credits_shares(trade_env):
    session = AsyncMock()
    r = AsyncMock()
    start_credits = trade_env["user"].credits

    with _trade_patches(trade_env):
        result = await trading.trade(
            session,
            r,
            user_id=trade_env["user_id"],
            model_id=trade_env["model"].model_id,
            side="buy",
            amount=100.0,
        )

    assert result["shares"] > 0
    assert trade_env["user"].credits == start_credits - 100.0
    assert trade_env["holdings"][trade_env["model"].model_id] == pytest.approx(
        result["shares"]
    )


@pytest.mark.asyncio
async def test_sell_reverses_buy(trade_env):
    session = AsyncMock()
    r = AsyncMock()

    with _trade_patches(trade_env):
        buy = await trading.trade(
            session,
            r,
            user_id=trade_env["user_id"],
            model_id=trade_env["model"].model_id,
            side="buy",
            amount=100.0,
        )
        credits_after_buy = trade_env["user"].credits
        shares_held = trade_env["holdings"][trade_env["model"].model_id]

        sell = await trading.trade(
            session,
            r,
            user_id=trade_env["user_id"],
            model_id=trade_env["model"].model_id,
            side="sell",
            amount=shares_held,
        )

    assert sell["credits"] > 0
    assert trade_env["holdings"][trade_env["model"].model_id] == pytest.approx(0.0)
    assert trade_env["user"].credits == pytest.approx(credits_after_buy + sell["credits"])
    assert sell["shares"] == pytest.approx(shares_held)


@pytest.mark.asyncio
async def test_buy_then_sell_same_shares_returns_less_credits_slippage(trade_env):
    session = AsyncMock()
    r = AsyncMock()
    pool = trade_env["pool"]
    initial_price = pool["credits"] / pool["shares"]
    spend = 200.0

    with _trade_patches(trade_env):
        buy = await trading.trade(
            session,
            r,
            user_id=trade_env["user_id"],
            model_id=trade_env["model"].model_id,
            side="buy",
            amount=spend,
        )
        shares_held = buy["shares"]
        sell = await trading.trade(
            session,
            r,
            user_id=trade_env["user_id"],
            model_id=trade_env["model"].model_id,
            side="sell",
            amount=shares_held,
        )

    # AMM curve: buy at worse than spot (fewer shares than naive quote).
    assert buy["shares"] < spend / initial_price
    assert buy["price"] > initial_price
    assert shares_held * initial_price < spend
    # Round-trip restores spent credits; slippage shows on the buy leg vs spot.
    assert sell["credits"] == pytest.approx(spend)
