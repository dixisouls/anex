"""
Market dynamics unit tests (no live DB).

    EMBEDDINGS_FAKE=1 WEAVE_DISABLED=1 pytest tests/0007_market_dynamics.py -v
"""

import random
from unittest.mock import AsyncMock, patch

import pytest

from backend.market import dynamics, exchange, registry


def test_compute_raw_earnings_zero_at_baseline():
    raw = dynamics.compute_raw_earnings(0.62)
    assert abs(raw) < 1e-9


def test_fundamental_update_balanced():
    f0 = 20.0
    f_up = dynamics.update_fundamental(f0, dynamics.compute_raw_earnings(0.75))
    f_dn = dynamics.update_fundamental(f0, dynamics.compute_raw_earnings(0.50))
    assert f_up > f0
    assert f_dn < f0


def test_cap_award_from_hire():
    award = dynamics.compute_award(0.8, derived_price=50.0, hire_price=40.0)
    assert award <= 40.0 * 0.15 + 1e-9


def test_bid_below_ask():
    s, c = 1000.0, 20000.0
    bid, _ = dynamics.quote_sell(s, c)
    ask, _ = dynamics.quote_buy(s, c)
    mid = dynamics.pool_mid(s, c)
    assert bid < mid < ask


def test_spread_widens_on_shallow_pool():
    deep_bid, _ = dynamics.quote_sell(1000, 20000)
    deep_ask, _ = dynamics.quote_buy(1000, 20000)
    deep_mid = dynamics.pool_mid(1000, 20000)
    deep_spread = dynamics.spread_bps(deep_bid, deep_ask, deep_mid)

    shallow_bid, _ = dynamics.quote_sell(100, 2000)
    shallow_ask, _ = dynamics.quote_buy(100, 2000)
    shallow_mid = dynamics.pool_mid(100, 2000)
    shallow_spread = dynamics.spread_bps(shallow_bid, shallow_ask, shallow_mid)
    assert shallow_spread > deep_spread


def test_gbm_path_reaches_target():
    rng = random.Random(7)
    path = dynamics.generate_gbm_path(20.0, 24.0, steps=120, tier="flash", rng=rng)
    assert len(path) == 120
    assert path[0] == 20.0
    assert path[-1] == 24.0
    # Not a straight line: at least one non-monotonic step
    diffs = [path[i + 1] - path[i] for i in range(len(path) - 2)]
    assert max(diffs) != min(diffs) or any(abs(d) > 1e-6 for d in diffs)


def test_arb_pulls_toward_fundamental():
    rng = random.Random(1)
    s, c = 1000.0, 22000.0  # price 22
    fundamental = 20.0
    amount = dynamics.arb_pool_adjustment(s, c, fundamental, "flash", 2.0, rng)
    assert amount < 0  # pool credits should drop to pull price down


def test_aggregate_bars_ohlc():
    ticks = [
        {"price": 10.0, "ts": "2026-06-07T10:00:00+00:00"},
        {"price": 12.0, "ts": "2026-06-07T10:00:30+00:00"},
        {"price": 9.0, "ts": "2026-06-07T10:00:45+00:00"},
    ]
    bars = registry.aggregate_bars(ticks, interval_s=60, limit=10)
    assert len(bars) == 1
    bar = bars[0]
    assert bar["h"] == 12.0
    assert bar["l"] == 9.0
    assert bar["o"] == 10.0
    assert bar["c"] == 9.0


@pytest.mark.asyncio
async def test_inject_arb_moves_pool():
    from backend.db.models import Model as ModelORM

    model = ModelORM(
        model_id="gemini-3.5-flash",
        name="Gemini 3.5 Flash",
        provider="gcp",
        tier="flash",
        executable=True,
        pool_shares=1000.0,
        pool_credits=24000.0,
        ipo_price=20.0,
    )
    state = {"shares": 1000.0, "credits": 24000.0}

    async def get_model(_session, model_id):
        model.pool_shares = state["shares"]
        model.pool_credits = state["credits"]
        return model

    async def update_pool(_session, model_id, *, shares, credits):
        state["shares"] = shares
        state["credits"] = credits

    session = AsyncMock()
    r = AsyncMock()
    r.hget = AsyncMock(return_value=b"20.0")

    with (
        patch("backend.market.exchange.repo.get_model", get_model),
        patch("backend.market.exchange.repo.update_model_pool", update_pool),
        patch("backend.market.exchange.registry.bump_session_stats", AsyncMock()),
        patch("backend.market.exchange.registry.project_model", AsyncMock()),
        patch("backend.market.exchange.registry.append_price_tick", AsyncMock()),
        patch("backend.market.exchange.registry.get_fundamental", AsyncMock(return_value=20.0)),
        patch("backend.market.exchange.bus.publish", AsyncMock()),
    ):
        old = state["credits"] / state["shares"]
        moved = await exchange.inject_arb(
            session, r, model_id="gemini-3.5-flash", dt=2.0, rng=random.Random(0)
        )
        new = state["credits"] / state["shares"]
        assert moved
        assert new != old
