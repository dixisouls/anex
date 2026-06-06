"""
Offline sim decision tests (no live OpenAI).

    EMBEDDINGS_FAKE=1 WEAVE_DISABLED=1 pytest tests/test_sim_decision.py -v
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from backend.sim import runner as sim_runner


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


def test_parse_bad_json_returns_hold():
    assert sim_runner.parse_investor_response("not json at all", {"gemini-3.5-flash"}) == {
        "action": "hold"
    }


def test_parse_invalid_model_returns_hold():
    raw = '{"model_id":"unknown","side":"buy","amount":50}'
    assert sim_runner.parse_investor_response(raw, {"gemini-3.5-flash"}) == {"action": "hold"}


def test_parse_valid_trade():
    raw = '{"model_id":"gemini-3.5-flash","side":"buy","amount":50}'
    assert sim_runner.parse_investor_response(raw, {"gemini-3.5-flash"}) == {
        "model_id": "gemini-3.5-flash",
        "side": "buy",
        "amount": 50.0,
    }


def test_trade_from_decision_caps_amount():
    decision = {"model_id": "gemini-3.5-flash", "side": "buy", "amount": 500.0}
    trade = sim_runner.trade_from_decision(decision, trade_cap=100.0)
    assert trade == {"model_id": "gemini-3.5-flash", "side": "buy", "amount": 100.0}


def test_trade_from_decision_hold_returns_none():
    assert sim_runner.trade_from_decision({"action": "hold"}, trade_cap=100.0) is None


@pytest.mark.asyncio
async def test_investor_loop_iteration_caps_trade(monkeypatch):
    """Monkeypatched decision with huge amount is capped before POST /trade."""
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

    monkeypatch.setattr(
        sim_runner,
        "investor_decision",
        lambda market, pf: {
            "model_id": "gemini-3.5-flash",
            "side": "buy",
            "amount": 500.0,
        },
    )
    monkeypatch.setattr(sim_runner.httpx, "AsyncClient", lambda **kw: FakeClient())
    monkeypatch.setattr(sim_runner.asyncio, "sleep", AsyncMock(side_effect=asyncio.CancelledError))

    with pytest.raises(asyncio.CancelledError):
        await sim_runner._investor_loop("http://test", "u1", 1.0)

    assert len(posted) == 1
    assert posted[0]["amount"] == sim_runner.TRADE_CAP
    assert posted[0]["user_id"] == "u1"


@pytest.mark.asyncio
async def test_investor_loop_bad_json_holds(monkeypatch):
    posted: list[dict] = []

    class FakeResponse:
        def json(self):
            return CANNED_MARKET if not hasattr(self, "_pf") else CANNED_PORTFOLIO

        def raise_for_status(self):
            return None

    class FakeClient:
        _n = 0

        async def get(self, path):
            self._n += 1
            r = FakeResponse()
            if "portfolio" in path:
                r._pf = True
            return r

        async def post(self, path, json=None):
            posted.append(json)
            return FakeResponse()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    monkeypatch.setattr(
        sim_runner,
        "investor_decision",
        lambda market, pf: {"action": "hold"},
    )
    monkeypatch.setattr(sim_runner.httpx, "AsyncClient", lambda **kw: FakeClient())
    monkeypatch.setattr(sim_runner.asyncio, "sleep", AsyncMock(side_effect=asyncio.CancelledError))

    with pytest.raises(asyncio.CancelledError):
        await sim_runner._investor_loop("http://test", "u1", 1.0)

    assert posted == []
