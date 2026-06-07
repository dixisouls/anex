"""
LLM sim investor tests (mocked OpenAI, no network).

    WEAVE_DISABLED=1 EMBEDDINGS_FAKE=1 pytest tests/test_llm_investor.py -v
"""

import asyncio
import json
import random
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.config import OPENAI_INVESTOR_TEMPERATURE
from backend.sim import llm_investor, runner as sim_runner
from backend.sim import strategies

MARKET = {
    "models": [
        {
            "model_id": "AAA",
            "name": "Model A",
            "price": 20.0,
            "bid": 19.8,
            "ask": 20.2,
            "fundamental": 18.0,
            "spread_bps": 20.0,
            "depth": 500.0,
            "vs_fair_pct": 11.1,
        },
        {
            "model_id": "BBB",
            "name": "Model B",
            "price": 10.0,
            "bid": 9.9,
            "ask": 10.1,
            "fundamental": 12.0,
            "spread_bps": 15.0,
            "depth": 300.0,
            "vs_fair_pct": -16.7,
        },
    ],
}

PORTFOLIO = {
    "credits": 200.0,
    "holdings": [{"model_id": "AAA", "shares": 5.0, "price": 20.0, "value": 100.0}],
    "holdings_value": 100.0,
    "total": 300.0,
}


def test_build_snapshot_includes_pf_ratio():
    snap = llm_investor.build_snapshot(MARKET, PORTFOLIO)
    assert len(snap["models"]) == 2
    aaa = next(m for m in snap["models"] if m["model_id"] == "AAA")
    assert aaa["pf_ratio"] == pytest.approx(round(20.0 / 18.0, 4))
    assert snap["portfolio"]["credits"] == 200.0
    assert snap["portfolio"]["total"] == 300.0
    assert snap["portfolio_hints"]["can_sell"] is True
    assert "AAA" in snap["portfolio_hints"]["held_model_ids"]


def test_build_snapshot_shuffles_models_with_rng():
    order_a = [
        m["model_id"]
        for m in llm_investor.build_snapshot(MARKET, PORTFOLIO, rng=random.Random(0))[
            "models"
        ]
    ]
    order_b = [
        m["model_id"]
        for m in llm_investor.build_snapshot(MARKET, PORTFOLIO, rng=random.Random(1))[
            "models"
        ]
    ]
    assert set(order_a) == {"AAA", "BBB"}
    assert set(order_b) == {"AAA", "BBB"}
    assert order_a != order_b


@pytest.mark.asyncio
async def test_enrich_snapshot_fetches_history():
    history = [{"ts": "t1", "price": 19.0}, {"ts": "t2", "price": 20.0}]

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

        def raise_for_status(self):
            return None

    class FakeClient:
        async def get(self, path, params=None):
            assert "/models/AAA/history" in path or "/models/BBB/history" in path
            return FakeResponse(history)

    snap = llm_investor.build_snapshot(MARKET, PORTFOLIO)
    enriched = await llm_investor.enrich_snapshot(FakeClient(), snap)
    for model in enriched["models"]:
        assert model["history"] == history
        assert "signals" in model
        assert "momentum_pct" in model["signals"]


def test_validate_decision_hold():
    assert (
        llm_investor.validate_decision({"action": "hold"}, MARKET, PORTFOLIO)
        == {"action": "hold"}
    )


def test_validate_decision_caps_buy_by_credits_and_trade_cap():
    d = llm_investor.validate_decision(
        {"model_id": "BBB", "side": "buy", "amount": 500.0},
        MARKET,
        PORTFOLIO,
        trade_cap=100.0,
    )
    assert d == {"model_id": "BBB", "side": "buy", "amount": 100.0}

    d2 = llm_investor.validate_decision(
        {"model_id": "BBB", "side": "buy", "amount": 50.0},
        MARKET,
        {"credits": 30.0, "holdings": []},
        trade_cap=100.0,
    )
    assert d2 == {"model_id": "BBB", "side": "buy", "amount": 30.0}


def test_validate_decision_buy_too_small_holds():
    d = llm_investor.validate_decision(
        {"model_id": "BBB", "side": "buy", "amount": 3.0},
        MARKET,
        {"credits": 3.0, "holdings": []},
        trade_cap=100.0,
    )
    assert d == {"action": "hold"}


def test_validate_decision_sell_caps_by_holdings():
    d = llm_investor.validate_decision(
        {"model_id": "AAA", "side": "sell", "amount": 50.0},
        MARKET,
        PORTFOLIO,
        trade_cap=100.0,
    )
    assert d == {"model_id": "AAA", "side": "sell", "amount": 5.0}


def test_validate_decision_invalid_model_holds():
    d = llm_investor.validate_decision(
        {"model_id": "ZZZ", "side": "buy", "amount": 50.0},
        MARKET,
        PORTFOLIO,
        trade_cap=100.0,
    )
    assert d == {"action": "hold"}


def test_decision_schema_is_flat_object():
    assert "oneOf" not in llm_investor.DECISION_SCHEMA
    assert llm_investor.DECISION_SCHEMA["type"] == "object"
    assert set(llm_investor.DECISION_SCHEMA["properties"]) == {
        "action",
        "model_id",
        "side",
        "amount",
    }


def test_normalize_llm_decision_maps_trade_and_hold():
    hold = {
        "action": "hold",
        "model_id": None,
        "side": None,
        "amount": 0,
    }
    assert llm_investor._normalize_llm_decision(hold) == {"action": "hold"}

    trade = {
        "action": "trade",
        "model_id": "BBB",
        "side": "buy",
        "amount": 40.0,
    }
    assert llm_investor._normalize_llm_decision(trade) == {
        "model_id": "BBB",
        "side": "buy",
        "amount": 40.0,
    }


def test_llm_decide_parse_failure_returns_hold():
    with patch("openai.OpenAI") as mock_cls:
        mock_cls.return_value.responses.create.side_effect = RuntimeError("boom")
        assert llm_investor.llm_decide(strategies.VALUE, {}) == {"action": "hold"}


def test_llm_decide_returns_structured_trade():
    trade = {
        "action": "trade",
        "model_id": "BBB",
        "side": "buy",
        "amount": 40.0,
    }

    class FakeResp:
        output_text = json.dumps(trade)

    with patch("openai.OpenAI") as mock_cls:
        mock_cls.return_value.responses.create.return_value = FakeResp()
        out = llm_investor.llm_decide(strategies.MOMENTUM, {"models": []})
    assert out == {"model_id": "BBB", "side": "buy", "amount": 40.0}


def test_llm_decide_passes_temperature_and_traits_in_prompt():
    trade = {
        "action": "hold",
        "model_id": None,
        "side": None,
        "amount": 0,
    }

    class FakeResp:
        output_text = json.dumps(trade)

    rng = random.Random(42)
    snap = llm_investor.build_snapshot(MARKET, PORTFOLIO, rng=rng)
    with patch("openai.OpenAI") as mock_cls:
        mock_cls.return_value.responses.create.return_value = FakeResp()
        llm_investor.llm_decide(strategies.CONTRARIAN, snap, rng=rng)
        kwargs = mock_cls.return_value.responses.create.call_args.kwargs
        assert kwargs["temperature"] == OPENAI_INVESTOR_TEMPERATURE
        prompt = kwargs["input"]
        assert "contrarian" in prompt.lower() or "Contrarian" in prompt
        assert "do not herd" in prompt.lower()
        assert "favorite_tier" in prompt


@pytest.mark.asyncio
async def test_investor_loop_llm_mode(monkeypatch):
    posted: list[dict] = []

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

        def raise_for_status(self):
            return None

    canned_market = {
        "models": [{"model_id": "gemini-3.5-flash", "price": 20.0, "fundamental": 18.0}],
        "history": [],
    }
    canned_pf = {"credits": 500.0, "holdings": [], "holdings_value": 0.0, "total": 500.0}

    class FakeClient:
        async def get(self, path, params=None):
            if path == "/market":
                return FakeResponse(canned_market)
            if path.startswith("/portfolio/"):
                return FakeResponse(canned_pf)
            if "/history" in path:
                return FakeResponse([{"ts": "t", "price": 19.0}])
            raise AssertionError(path)

        async def post(self, path, json=None):
            posted.append(json)
            return FakeResponse({})

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    monkeypatch.setattr(
        sim_runner.llm_investor,
        "llm_decide",
        lambda *a, **k: {
            "model_id": "gemini-3.5-flash",
            "side": "buy",
            "amount": 500.0,
        },
    )
    monkeypatch.setattr(sim_runner.httpx, "AsyncClient", lambda **kw: FakeClient())
    monkeypatch.setattr(
        sim_runner.asyncio,
        "to_thread",
        AsyncMock(
            side_effect=lambda fn, *a, **k: fn(*a, **k),
        ),
    )
    monkeypatch.setattr(
        sim_runner.asyncio, "sleep", AsyncMock(side_effect=asyncio.CancelledError)
    )

    with pytest.raises(asyncio.CancelledError):
        await sim_runner._investor_loop(
            "http://test", "u1", 1.0, mode="llm", strategy=strategies.VALUE
        )

    assert len(posted) == 1
    assert posted[0]["amount"] == sim_runner.TRADE_CAP
    assert posted[0]["user_id"] == "u1"
