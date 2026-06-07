"""Algorithmic investor strategies for the market simulation.

Each sim investor is assigned a strategy. On every tick it reads the whole
market snapshot (current prices + rolling price history) and its own portfolio,
derives per-model signals, and picks ONE trade (or holds). Selection is a
softmax over per-model scores so volume spreads realistically across the whole
board instead of collapsing onto a single ticker.

Pure-Python and fast: no LLM / network calls here.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from backend.config import DEPTH_FRACTION

# Strategy identifiers
VALUE = "value"
MOMENTUM = "momentum"
CONTRARIAN = "contrarian"
NOISE = "noise"
MARKET_MAKER = "market_maker"
STAT_ARB = "stat_arb"

STRATEGIES: tuple[str, ...] = (
    MOMENTUM,
    MOMENTUM,
    VALUE,
    VALUE,
    STAT_ARB,
    STAT_ARB,
    CONTRARIAN,
    MARKET_MAKER,
    NOISE,
)

# Tuning constants
_MA_WINDOW = 20
_MOMENTUM_K = 10
_MIN_TRADE = 5.0  # don't bother with dust trades
_EPSILON = 1e-3  # tie-break / exploration noise
_SOFTMAX_TEMP = 0.6
_TARGET_INVESTED = 0.6  # fraction of net worth investors aim to keep deployed
_PF_RICH = 1.08
_PF_CHEAP = 0.92


@dataclass
class Signal:
    model_id: str
    price: float
    fundamental: float
    ma: float
    momentum: float  # fractional return over the recent window
    zscore: float  # (price - ma) / std, how rich/cheap vs its own mean
    vol: float  # stddev of recent prices (absolute)
    depth: float
    pf_ratio: float  # price / fundamental
    spread_bps: float


def _series_by_model(market: dict) -> dict[str, list[float]]:
    """Group the interleaved price history into per-model series (in order)."""
    series: dict[str, list[float]] = {}
    for tick in market.get("history", []) or []:
        mid = tick.get("model_id")
        price = tick.get("price")
        if mid is None or price is None:
            continue
        series.setdefault(mid, []).append(float(price))
    return series


def _stddev(values: list[float], mean: float) -> float:
    if len(values) < 2:
        return 0.0
    var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(max(var, 0.0))


def build_signals(market: dict) -> dict[str, Signal]:
    """Per-model signals derived from the market snapshot + price history."""
    series = _series_by_model(market)
    signals: dict[str, Signal] = {}

    for m in market.get("models", []) or []:
        mid = m.get("model_id")
        if mid is None:
            continue
        price = float(m.get("price", 0.0) or 0.0)
        if price <= 0:
            continue

        fundamental = float(m.get("fundamental", price) or price)
        depth = float(m.get("depth", 0.0) or 0.0)
        spread_bps = float(m.get("spread_bps", 0.0) or 0.0)
        pf_ratio = price / fundamental if fundamental > 0 else 1.0

        hist = series.get(mid, [])
        recent = (hist + [price])[-_MA_WINDOW:]
        ma = sum(recent) / len(recent) if recent else price
        vol = _stddev(recent, ma)
        zscore = (price - ma) / vol if vol > 1e-9 else 0.0

        if len(hist) >= 1:
            k = min(_MOMENTUM_K, len(hist))
            past = hist[-k]
            momentum = (price - past) / past if past > 1e-9 else 0.0
        else:
            momentum = 0.0

        signals[mid] = Signal(
            model_id=mid,
            price=price,
            fundamental=fundamental,
            ma=ma,
            momentum=momentum,
            zscore=zscore,
            vol=vol,
            depth=depth,
            pf_ratio=pf_ratio,
            spread_bps=spread_bps,
        )

    return signals


def _buy_score(strategy: str, sig: Signal, rng: random.Random) -> float:
    """Higher = more attractive to buy under this strategy."""
    jitter = rng.uniform(-_EPSILON, _EPSILON)
    if strategy == VALUE:
        return -sig.zscore + jitter
    if strategy == MOMENTUM:
        return sig.momentum * 10.0 + jitter
    if strategy == CONTRARIAN:
        return -sig.momentum * 10.0 + jitter
    if strategy == STAT_ARB:
        # Buy when market trades below fair value.
        mispricing = (sig.fundamental - sig.price) / max(sig.fundamental, 1e-9)
        return mispricing * 12.0 - sig.spread_bps * 0.001 + jitter
    if strategy == MARKET_MAKER:
        return -sig.zscore * 0.3 + jitter
    return rng.random()


def score_models(
    strategy: str, signals: dict[str, Signal], rng: random.Random
) -> dict[str, float]:
    return {mid: _buy_score(strategy, sig, rng) for mid, sig in signals.items()}


def softmax_pick(
    scores: dict[str, float], rng: random.Random, temperature: float = _SOFTMAX_TEMP
) -> str | None:
    """Weighted-random selection across ALL candidates (not argmax)."""
    if not scores:
        return None
    items = list(scores.items())
    t = max(temperature, 1e-6)
    mx = max(s for _, s in items)
    weights = [math.exp((s - mx) / t) for _, s in items]
    total = sum(weights)
    if total <= 0:
        return rng.choice([mid for mid, _ in items])
    r = rng.random() * total
    upto = 0.0
    for (mid, _), w in zip(items, weights):
        upto += w
        if r <= upto:
            return mid
    return items[-1][0]


def _holdings_map(portfolio: dict) -> dict[str, float]:
    out: dict[str, float] = {}
    for h in portfolio.get("holdings", []) or []:
        mid = h.get("model_id")
        shares = float(h.get("shares", 0.0) or 0.0)
        if mid is not None and shares > 0:
            out[mid] = shares
    return out


def _depth_cap(sig: Signal | None, trade_cap: float) -> float:
    if sig is None or sig.depth <= 0:
        return trade_cap
    return min(trade_cap, sig.depth * DEPTH_FRACTION)


def decide(
    strategy: str,
    market: dict,
    portfolio: dict,
    rng: random.Random,
    *,
    trade_cap: float,
) -> dict:
    """Pick one trade for this investor, or hold.

    Returns the same schema the runner already understands:
        {"model_id": str, "side": "buy"|"sell", "amount": float}
        {"action": "hold"}
    """
    signals = build_signals(market)
    if not signals:
        return {"action": "hold"}

    credits = float(portfolio.get("credits", 0.0) or 0.0)
    holdings = _holdings_map(portfolio)

    can_buy = credits >= _MIN_TRADE
    can_sell = len(holdings) > 0

    if not can_buy and not can_sell:
        return {"action": "hold"}

    holdings_value = sum(
        sh * signals[mid].price for mid, sh in holdings.items() if mid in signals
    )
    total_value = credits + holdings_value
    invested = (holdings_value / total_value) if total_value > 0 else 0.0
    pull = 1.0 if strategy == MARKET_MAKER else 1.5
    prefer_sell_prob = 0.5 + (invested - _TARGET_INVESTED) * pull

    held_rich = any(
        (sig := signals.get(mid)) is not None and sig.zscore > 0.5
        for mid in holdings
    )
    if held_rich:
        prefer_sell_prob += 0.15

    # Price vs fundamental overlay: shed rich names, buy cheap ones.
    pf_sells = [
        mid
        for mid in holdings
        if (sig := signals.get(mid)) is not None and sig.pf_ratio > _PF_RICH
    ]
    pf_buys = [
        mid
        for mid, sig in signals.items()
        if sig.pf_ratio < _PF_CHEAP
    ]
    if pf_sells:
        prefer_sell_prob += 0.12
    if pf_buys and strategy in (STAT_ARB, VALUE, CONTRARIAN):
        prefer_sell_prob -= 0.1

    prefer_sell_prob = max(0.05, min(0.95, prefer_sell_prob))
    do_sell = can_sell and (not can_buy or rng.random() < prefer_sell_prob)

    if do_sell:
        sell_scores: dict[str, float] = {}
        for mid, shares in holdings.items():
            sig = signals.get(mid)
            base = -_buy_score(strategy, sig, rng) if sig else rng.random()
            if sig and sig.pf_ratio > _PF_RICH:
                base += 0.5
            sell_scores[mid] = base
        pick = softmax_pick(sell_scores, rng)
        if pick is None:
            return {"action": "hold"}
        held = holdings[pick]
        sig = signals.get(pick)
        px = sig.price if sig else 0.0
        cap = _depth_cap(sig, trade_cap)
        if px > 0:
            notional = min(cap, held * px) * rng.uniform(0.25, 1.0)
            amount = notional / px
        else:
            amount = held * rng.uniform(0.25, 1.0)
        amount = min(amount, held)
        if amount <= 0:
            return {"action": "hold"}
        return {"model_id": pick, "side": "sell", "amount": amount}

    scores = score_models(strategy, signals, rng)
    pick = softmax_pick(scores, rng)
    if pick is None:
        return {"action": "hold"}
    sig = signals.get(pick)
    cap = _depth_cap(sig, trade_cap)
    budget = min(cap, credits)
    amount = budget * rng.uniform(0.2, 1.0)
    if amount < _MIN_TRADE:
        amount = min(_MIN_TRADE, budget)
    if amount < _MIN_TRADE:
        return {"action": "hold"}
    return {"model_id": pick, "side": "buy", "amount": amount}
