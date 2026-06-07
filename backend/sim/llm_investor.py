"""LLM-based sim investor decisions via OpenAI structured JSON output."""

from __future__ import annotations

import json
import logging
import random
from typing import Any
from urllib.parse import quote

import httpx
import weave

from backend.config import (
    OPENAI_INVESTOR_MODEL,
    OPENAI_INVESTOR_TEMPERATURE,
    TRADE_CAP,
)

logger = logging.getLogger(__name__)

_MIN_TRADE = 5.0
_HISTORY_LIMIT = 20
_MOMENTUM_WINDOW = 10

STRATEGY_PERSONAS: dict[str, str] = {
    "value": (
        "Value investor: prefer models trading below fundamental fair value; "
        "trim names rich vs fair."
    ),
    "momentum": (
        "Momentum trader: buy recent winners, sell laggards using price history."
    ),
    "contrarian": "Contrarian: fade recent moves — buy dips, sell rips.",
    "noise": (
        "Retail-style diversified trader: spread risk, moderate sizes, hold when unsure."
    ),
    "market_maker": (
        "Market maker: provide liquidity — lean buy when cheap, sell when rich vs fair."
    ),
    "stat_arb": (
        "Stat-arb: exploit price vs fundamental mispricings and mean-reversion."
    ),
}

STRATEGY_FOCUS: dict[str, str] = {
    "value": "Favor low pf_ratio (cheap vs fundamental). Sell holdings with pf_ratio > 1.08.",
    "momentum": "Favor positive momentum_pct in history. Sell laggards you hold.",
    "contrarian": "Favor negative momentum_pct (dips). Sell names that ripped recently.",
    "noise": "Rotate across tiers; avoid concentrating in one model_id.",
    "market_maker": "Buy below fair (pf_ratio < 1), sell above fair on holdings.",
    "stat_arb": "Buy largest negative vs_fair_pct; sell rich names in your book.",
}

DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["hold", "trade"]},
        "model_id": {"type": ["string", "null"]},
        "side": {"type": ["string", "null"], "enum": ["buy", "sell", None]},
        "amount": {"type": "number", "minimum": 0},
    },
    "required": ["action", "model_id", "side", "amount"],
    "additionalProperties": False,
}


def _normalize_llm_decision(raw: dict) -> dict:
    """Map flat schema output to hold or trade dict for validate_decision."""
    action = raw.get("action")
    if action == "hold":
        return {"action": "hold"}
    if action == "trade" or (action is None and raw.get("model_id")):
        return {
            "model_id": raw.get("model_id"),
            "side": raw.get("side"),
            "amount": raw.get("amount"),
        }
    return {"action": "hold"}


def _investor_traits(rng: random.Random) -> dict[str, Any]:
    """Stable per-investor personality knobs derived from the loop RNG."""
    return {
        "favorite_tier": rng.choice(("pro", "flash", "lite")),
        "risk": rng.choice(("conservative", "balanced", "aggressive")),
        "focus": rng.choice(("diversified", "rotational", "single-theme")),
        "explore_pct": rng.randint(15, 45),
        "hold_bias_pct": rng.randint(10, 35),
    }


def _attach_signal_digest(model: dict) -> None:
    """Lightweight cues so strategies diverge on the same board."""
    history = model.get("history") or []
    prices = [float(h["price"]) for h in history if h.get("price") is not None]
    price = float(model.get("price", 0.0) or 0.0)
    if prices and price > 0:
        past = prices[-min(_MOMENTUM_WINDOW, len(prices))]
        momentum = (price - past) / past if past > 1e-9 else 0.0
    else:
        momentum = 0.0
    pf = float(model.get("pf_ratio", 1.0) or 1.0)
    model["signals"] = {
        "momentum_pct": round(momentum * 100.0, 2),
        "cheap_vs_fair": pf < 0.95,
        "rich_vs_fair": pf > 1.05,
    }


def _portfolio_hints(portfolio: dict) -> dict[str, Any]:
    holdings = portfolio.get("holdings", []) or []
    credits = float(portfolio.get("credits", 0.0) or 0.0)
    total = float(portfolio.get("total", credits) or credits)
    holdings_value = float(portfolio.get("holdings_value", 0.0) or 0.0)
    invested_pct = round(100.0 * holdings_value / total, 1) if total > 0 else 0.0
    held_ids = [h.get("model_id") for h in holdings if h.get("model_id")]
    return {
        "invested_pct": invested_pct,
        "held_model_ids": held_ids,
        "can_sell": bool(held_ids),
        "can_buy": credits >= _MIN_TRADE,
    }


def build_snapshot(
    market: dict, portfolio: dict, *, rng: random.Random | None = None
) -> dict:
    """Compact market + portfolio view for the investor prompt."""
    models_out: list[dict[str, Any]] = []
    for m in market.get("models", []) or []:
        mid = m.get("model_id")
        if mid is None:
            continue
        price = float(m.get("price", 0.0) or 0.0)
        fundamental = float(m.get("fundamental", price) or price)
        models_out.append(
            {
                "model_id": mid,
                "name": m.get("name", mid),
                "tier": m.get("tier"),
                "price": price,
                "bid": float(m.get("bid", price) or price),
                "ask": float(m.get("ask", price) or price),
                "fundamental": fundamental,
                "spread_bps": float(m.get("spread_bps", 0.0) or 0.0),
                "depth": float(m.get("depth", 0.0) or 0.0),
                "pf_ratio": round(price / fundamental, 4) if fundamental > 0 else 1.0,
                "vs_fair_pct": m.get("vs_fair_pct"),
            }
        )

    if rng is not None:
        rng.shuffle(models_out)

    holdings_out: list[dict[str, Any]] = []
    for h in portfolio.get("holdings", []) or []:
        mid = h.get("model_id")
        if mid is None:
            continue
        holdings_out.append(
            {
                "model_id": mid,
                "shares": float(h.get("shares", 0.0) or 0.0),
                "price": float(h.get("price", 0.0) or 0.0),
                "value": float(h.get("value", 0.0) or 0.0),
            }
        )

    credits = float(portfolio.get("credits", 0.0) or 0.0)
    pf_block = {
        "credits": credits,
        "holdings": holdings_out,
        "holdings_value": float(portfolio.get("holdings_value", 0.0) or 0.0),
        "total": float(portfolio.get("total", credits) or credits),
    }
    return {
        "models": models_out,
        "portfolio": pf_block,
        "portfolio_hints": _portfolio_hints(pf_block),
        "constraints": {
            "max_trade_amount": TRADE_CAP,
            "min_trade_amount": _MIN_TRADE,
        },
    }


async def enrich_snapshot(
    client: httpx.AsyncClient,
    snapshot: dict,
    *,
    history_limit: int = _HISTORY_LIMIT,
) -> dict:
    """Attach per-model recent price history via the public API."""
    enriched = json.loads(json.dumps(snapshot))
    for model in enriched.get("models", []):
        mid = model.get("model_id")
        if not mid:
            continue
        path = f"/models/{quote(mid, safe='')}/history"
        try:
            resp = await client.get(path, params={"limit": history_limit})
            resp.raise_for_status()
            ticks = resp.json()
            model["history"] = [
                {"ts": t.get("ts"), "price": t.get("price")} for t in ticks
            ]
        except Exception:
            logger.debug("history fetch failed model=%s", mid, exc_info=True)
            model["history"] = []
        _attach_signal_digest(model)
    return enriched


def _build_prompt(strategy: str, snapshot: dict, traits: dict[str, Any]) -> str:
    persona = STRATEGY_PERSONAS.get(
        strategy, f"Sim investor using the {strategy} style."
    )
    focus = STRATEGY_FOCUS.get(strategy, "Trade the full universe; avoid herding.")
    hints = snapshot.get("portfolio_hints", {})
    hold_note = (
        f"Holding is fine (~{traits['hold_bias_pct']}% of the time you would pass)."
    )
    sell_note = ""
    if hints.get("can_sell"):
        sell_note = (
            "You hold positions — consider trimming winners, rotating, or selling "
            "rich names; do not only buy.\n"
        )
    elif hints.get("can_buy"):
        sell_note = (
            "You have cash but no shares yet — buys are OK, but spread across "
            "model_ids and tiers; do not default to the cheapest ticker.\n"
        )

    return (
        f"You are one of many independent simulated investors. Style: {persona}\n"
        f"Strategy lens: {focus}\n"
        f"Your traits: favorite_tier={traits['favorite_tier']}, "
        f"risk={traits['risk']}, focus={traits['focus']}, "
        f"explore_bias={traits['explore_pct']}%.\n\n"
        "Decide ONE action for this tick. Other investors have different styles — "
        "do not herd into the same model_id.\n"
        f"{hold_note}\n"
        f"{sell_note}"
        '- Hold: {"action": "hold", "model_id": null, "side": null, "amount": 0}.\n'
        '- Trade: {"action": "trade", "model_id": "<id>", "side": "buy"|"sell", '
        '"amount": number}.\n'
        "  BUY amount = credits to spend. SELL amount = shares to sell "
        "(only models in portfolio.holdings).\n"
        "Use realistic sizes between min and max trade; vary model_id across the board.\n\n"
        f"Market and portfolio JSON:\n{json.dumps(snapshot, indent=2)}"
    )


@weave.op
def llm_decide(
    strategy: str,
    snapshot: dict,
    *,
    rng: random.Random | None = None,
) -> dict:
    """OpenAI structured output: hold or one trade (unvalidated)."""
    rng = rng or random.Random()
    traits = _investor_traits(rng)
    try:
        from openai import OpenAI

        resp = (
            OpenAI()
            .responses.create(
                model=OPENAI_INVESTOR_MODEL,
                input=_build_prompt(strategy, snapshot, traits),
                temperature=OPENAI_INVESTOR_TEMPERATURE,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "investor_decision",
                        "strict": True,
                        "schema": DECISION_SCHEMA,
                    }
                },
            )
        )
        raw = json.loads(resp.output_text)
        if not isinstance(raw, dict):
            return {"action": "hold"}
        return _normalize_llm_decision(raw)
    except Exception:
        logger.exception("llm_decide failed; holding")
        return {"action": "hold"}


def _valid_model_ids(market: dict) -> set[str]:
    return {
        m["model_id"]
        for m in market.get("models", []) or []
        if m.get("model_id") is not None
    }


def _holdings_map(portfolio: dict) -> dict[str, float]:
    out: dict[str, float] = {}
    for h in portfolio.get("holdings", []) or []:
        mid = h.get("model_id")
        shares = float(h.get("shares", 0.0) or 0.0)
        if mid is not None and shares > 0:
            out[mid] = shares
    return out


def validate_decision(
    decision: dict,
    market: dict,
    portfolio: dict,
    *,
    trade_cap: float = TRADE_CAP,
) -> dict:
    """Normalize LLM output: valid model, capped size, hold on bad input."""
    if not isinstance(decision, dict):
        return {"action": "hold"}

    if decision.get("action") == "hold":
        return {"action": "hold"}

    model_id = decision.get("model_id")
    side = decision.get("side")
    amount = decision.get("amount")

    valid_ids = _valid_model_ids(market)
    if model_id not in valid_ids:
        return {"action": "hold"}
    if side not in ("buy", "sell"):
        return {"action": "hold"}
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return {"action": "hold"}
    if amount <= 0:
        return {"action": "hold"}

    credits = float(portfolio.get("credits", 0.0) or 0.0)
    holdings = _holdings_map(portfolio)
    amount = min(amount, trade_cap)

    if side == "buy":
        amount = min(amount, credits)
        if amount < _MIN_TRADE:
            return {"action": "hold"}
        return {"model_id": model_id, "side": "buy", "amount": amount}

    held = holdings.get(model_id, 0.0)
    if held <= 0:
        return {"action": "hold"}
    amount = min(amount, held)
    if amount <= 0:
        return {"action": "hold"}
    return {"model_id": model_id, "side": "sell", "amount": amount}
