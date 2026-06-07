"""
Offline sim decision tests (no live OpenAI / network).

    EMBEDDINGS_FAKE=1 WEAVE_DISABLED=1 pytest tests/test_sim_decision.py -v
"""

import asyncio
import random
from collections import Counter
from unittest.mock import AsyncMock

import pytest

from backend.sim import runner as sim_runner
from backend.sim import strategies


CANNED_MARKET = {
    "models": [
        {"model_id": "gemini-3.5-flash", "price": 20.0},
        {"model_id": "gpt-4.1-mini", "price": 15.0},
    ],
    "history": [],
}

CANNED_PORTFOLIO = {
    "user_id": "u1",
    "credits": 500.0,
    "holdings": [],
    "holdings_value": 0.0,
    "total": 500.0,
}


def _market_with_history():
    models = [
        {"model_id": "AAA", "price": 30.0, "fundamental": 28.0, "depth": 500.0},
        {"model_id": "BBB", "price": 10.0, "fundamental": 11.0, "depth": 300.0},
        {"model_id": "CCC", "price": 50.0, "fundamental": 48.0, "depth": 800.0},
        {"model_id": "DDD", "price": 8.0, "fundamental": 9.0, "depth": 200.0},
    ]
    # Build some history so momentum / zscore are non-trivial.
    history = []
    for mid, base in (("AAA", 20.0), ("BBB", 12.0), ("CCC", 45.0), ("DDD", 9.0)):
        for j in range(15):
            history.append({"model_id": mid, "price": base + j * 0.3})
    return {"models": models, "history": history}


# ── trade_from_decision (capping) ────────────────────────────────────────────


def test_trade_from_decision_caps_amount():
    decision = {"model_id": "gemini-3.5-flash", "side": "buy", "amount": 500.0}
    trade = sim_runner.trade_from_decision(decision, trade_cap=100.0)
    assert trade == {"model_id": "gemini-3.5-flash", "side": "buy", "amount": 100.0}


def test_trade_from_decision_hold_returns_none():
    assert sim_runner.trade_from_decision({"action": "hold"}, trade_cap=100.0) is None


# ── build_signals ────────────────────────────────────────────────────────────


def test_build_signals_covers_all_models():
    market = _market_with_history()
    signals = strategies.build_signals(market)
    assert set(signals) == {"AAA", "BBB", "CCC", "DDD"}
    for sig in signals.values():
        assert sig.price > 0
        assert sig.ma > 0
        assert sig.fundamental > 0
        assert sig.pf_ratio > 0


def test_build_signals_skips_zero_price():
    market = {"models": [{"model_id": "X", "price": 0.0}], "history": []}
    assert strategies.build_signals(market) == {}


# ── decide: diversity + schema ───────────────────────────────────────────────


def test_decide_spreads_across_models():
    """Across many seeded runs, buys should hit more than one ticker."""
    market = _market_with_history()
    picks = Counter()
    for seed in range(200):
        rng = random.Random(seed)
        d = strategies.decide(
            strategies.NOISE, market, CANNED_PORTFOLIO, rng, trade_cap=100.0
        )
        if d.get("side") == "buy":
            picks[d["model_id"]] += 1
    assert len(picks) >= 3, f"expected spread, got {picks}"


def test_decide_respects_no_credits_and_no_holdings():
    market = _market_with_history()
    pf = {"credits": 0.0, "holdings": []}
    d = strategies.decide(strategies.VALUE, market, pf, random.Random(1), trade_cap=100.0)
    assert d == {"action": "hold"}


def test_decide_sells_only_held_models():
    market = _market_with_history()
    pf = {
        "credits": 0.0,  # force sell path
        "holdings": [{"model_id": "CCC", "shares": 10.0}],
    }
    saw_sell = False
    for seed in range(50):
        d = strategies.decide(
            strategies.MOMENTUM, market, pf, random.Random(seed), trade_cap=100.0
        )
        if d.get("side") == "sell":
            saw_sell = True
            assert d["model_id"] == "CCC"
            assert 0 < d["amount"] <= 10.0
    assert saw_sell


def test_decide_returns_valid_schema():
    market = _market_with_history()
    for strat in strategies.STRATEGIES:
        d = strategies.decide(
            strat, market, CANNED_PORTFOLIO, random.Random(7), trade_cap=100.0
        )
        if d.get("action") == "hold":
            continue
        assert d["side"] in ("buy", "sell")
        assert d["model_id"] in {m["model_id"] for m in market["models"]}
        assert d["amount"] > 0


def test_decide_empty_market_holds():
    d = strategies.decide(
        strategies.VALUE, {"models": [], "history": []}, CANNED_PORTFOLIO,
        random.Random(0), trade_cap=100.0,
    )
    assert d == {"action": "hold"}


# ── _investor_loop integration (algorithmic path) ────────────────────────────


@pytest.mark.asyncio
async def test_investor_loop_iteration_caps_trade(monkeypatch):
    """A decision with a huge amount is capped before POST /trade."""
    posted: list[dict] = []

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

        def raise_for_status(self):
            return None

    class FakeClient:
        async def get(self, path):
            if path == "/market":
                return FakeResponse(CANNED_MARKET)
            if path == "/portfolio/u1":
                return FakeResponse(CANNED_PORTFOLIO)
            raise AssertionError(path)

        async def post(self, path, json=None):
            posted.append(json)
            return FakeResponse({})

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    monkeypatch.setattr(sim_runner, "SIM_INVESTOR_MODE", "math")
    monkeypatch.setattr(
        sim_runner.strategies,
        "decide",
        lambda *a, **k: {
            "model_id": "gemini-3.5-flash",
            "side": "buy",
            "amount": 500.0,
        },
    )
    monkeypatch.setattr(sim_runner.httpx, "AsyncClient", lambda **kw: FakeClient())
    monkeypatch.setattr(sim_runner.asyncio, "sleep", AsyncMock(side_effect=asyncio.CancelledError))

    with pytest.raises(asyncio.CancelledError):
        await sim_runner._investor_loop("http://test", "u1", 1.0, strategies.VALUE)

    assert len(posted) == 1
    assert posted[0]["amount"] == sim_runner.TRADE_CAP
    assert posted[0]["user_id"] == "u1"


@pytest.mark.asyncio
async def test_investor_loop_hold_posts_nothing(monkeypatch):
    posted: list[dict] = []

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

        def raise_for_status(self):
            return None

    class FakeClient:
        async def get(self, path):
            if path == "/market":
                return FakeResponse(CANNED_MARKET)
            return FakeResponse(CANNED_PORTFOLIO)

        async def post(self, path, json=None):
            posted.append(json)
            return FakeResponse({})

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    monkeypatch.setattr(sim_runner, "SIM_INVESTOR_MODE", "math")
    monkeypatch.setattr(
        sim_runner.strategies, "decide", lambda *a, **k: {"action": "hold"}
    )
    monkeypatch.setattr(sim_runner.httpx, "AsyncClient", lambda **kw: FakeClient())
    monkeypatch.setattr(sim_runner.asyncio, "sleep", AsyncMock(side_effect=asyncio.CancelledError))

    with pytest.raises(asyncio.CancelledError):
        await sim_runner._investor_loop("http://test", "u1", 1.0, strategies.NOISE)

    assert posted == []
