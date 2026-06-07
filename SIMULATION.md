# Anex — Simulation

Anex ships a **hybrid agent-based market simulation** so the marketplace and the exchange
feel alive without needing thousands of real users. Every simulated participant is an
independent async loop that drives the **same public API a human would** — it has no
backdoor access to internal state. The simulation exercises the full system: posting
goals, the broker pipeline, judging, settlement, and live trading.

This is itself a piece of the **multi-agent orchestration** story: dozens of autonomous
poster and investor agents act concurrently against a shared market, and the market's
behavior emerges from their interaction.

---

## What the simulation drives

```
                          ┌───────────────────────────────────────────┐
                          │                Public API                  │
   posters  ───────────▶  │  POST /task            (labor market)      │
   (OpenAI goals)         │  GET  /task/slots      (backpressure)      │
                          │  GET  /market /portfolio /models/.../history│
   investor cohorts ───▶  │  POST /trade           (asset market)      │
   (math + LLM)           └───────────────────────────────────────────┘
```

Two participant types: **posters** (create demand for agent work) and **investors**
(trade the model stocks). Sim users are ordinary `users` rows flagged `is_sim`, named
`sim-poster-*` / `sim-investor-*`, and started with the standard credit balance.

---

## Posters

A poster loop ([`backend/sim/runner.py`](backend/sim/runner.py)):

1. **Waits for a free broker slot** — polls `GET /task/slots` and only posts when the
   global task semaphore has capacity. This is real **backpressure**: posters never
   overwhelm the broker or the LLM providers.
2. **Invents a goal** — `gen_goal()` asks OpenAI for one realistic, varied work request
   (writing / coding / research, one line). Falls back to a fixed pool of goals if the
   call fails.
3. **Sizes a budget** — reads its live portfolio credits, capped by `POSTER_BUDGET_CAP`.
4. **Posts the task** — `POST /task`, which runs the full broker pipeline (decompose →
   recall → re-rank → hire → execute → judge → settle).

Posters run on a jittered cadence so they desynchronize.

---

## Investors: the hybrid model

This is the core of the simulation. Anex **blends two decision engines** so the market has
both realistic liquidity and realistic narrative trading:

| Engine | Who | Speed | How decisions are made |
|--------|-----|-------|------------------------|
| **Math** | market-makers, quants | fast (low cadence) | Pure-Python quant strategies over price history + fundamentals |
| **LLM** | retail, whales | slow (high cadence) | OpenAI structured-JSON decisions with per-investor personas |

Cheap, deterministic math agents trade frequently and provide liquidity; expensive LLM
agents trade rarely and add discretionary, persona-driven flow. Together they produce
volume and price action that neither alone would.

### Cohorts

Investors are organized into **role-based cohorts**
([`backend/sim/cohorts.py`](backend/sim/cohorts.py)). Each cohort shares a mode, a cadence,
a strategy palette, and an optional trade cap. The default hybrid mix:

| Cohort | Mode | Count (default) | Cadence | Strategies | Notes |
|--------|------|-----------------|---------|------------|-------|
| **mm** (market makers) | math | 8 | ~3s | market-maker, stat-arb | Fast liquidity |
| **quant** | math | 6 | ~6s | momentum, value, stat-arb | Systematic |
| **retail** | LLM | 20 | ~12s | noise, momentum, contrarian, value | Discretionary, diversified |
| **whale** | LLM | 4 | ~30s | value, momentum | Larger trades (higher cap) |

Cohorts flatten into one **assignment per investor** (strategy rotated within the cohort,
start times staggered so they don't fire in lockstep). The split is configurable via
environment variables (counts, cadences, whale trade cap), and a **legacy mode**
(`SIM_USE_COHORTS=0`) runs all investors with a single mode/strategy.

### The investor loop

Every tick an investor ([`runner.py::_investor_loop`](backend/sim/runner.py)) reads the
live `/market` and its `/portfolio`, decides one action (its engine differs by mode),
caps the trade size, and submits it via `POST /trade` — or holds. Cadence is jittered per
investor so order flow is spread out.

---

## Math strategies

[`backend/sim/strategies.py`](backend/sim/strategies.py) — pure Python, no network. On
each tick a strategy builds **per-model signals** from the market snapshot and rolling
price history:

- **moving average, momentum** (return over a recent window),
- **z-score** (how rich/cheap vs the model's own mean),
- **volatility, depth, spread**,
- **price/fundamental ratio** (`pf_ratio`).

Each strategy scores models differently:

| Strategy | Buys when… |
|----------|-----------|
| **value** | price is cheap vs its own mean (low z-score) |
| **momentum** | recent return is positive |
| **contrarian** | recent return is negative (fade the move) |
| **stat-arb** | price is below fundamental fair value |
| **market-maker** | leans into mild dislocations, provides two-sided liquidity |
| **noise** | random rotation across the board |

Selection is a **softmax over scores** (not argmax), so trades spread realistically across
the whole board instead of collapsing onto one ticker. A sell/buy bias is computed from how
far the portfolio's invested fraction is from a target, with overlays to shed rich names
(`pf_ratio` high) and accumulate cheap ones. Trade size is capped by both the cohort cap and
a fraction of pool **depth** so a single sim trade can't move an illiquid name too far.

---

## LLM strategies

[`backend/sim/llm_investor.py`](backend/sim/llm_investor.py) — OpenAI decisions as strict
structured JSON. For each tick:

1. **Build a compact snapshot** — for each model: price, bid/ask, fundamental, spread,
   depth, `pf_ratio`, `vs_fair_pct`; for the portfolio: credits, holdings, invested %,
   what it can buy/sell. Model order is shuffled so the LLM doesn't anchor on position.
2. **Enrich** — attach recent per-model price history (via the public `/history` endpoint)
   and a small signal digest (momentum %, cheap/rich vs fair).
3. **Persona + strategy lens** — each investor gets stable personality traits (favorite
   tier, risk appetite, focus, explore/hold biases) plus a strategy persona (value,
   momentum, contrarian, noise, market-maker, stat-arb). The prompt explicitly tells the
   investor that *other investors have different styles — don't herd into the same model*.
4. **Decide** — OpenAI Responses API with a **strict `json_schema`** returning
   `{action: hold|trade, model_id, side, amount}`.
5. **Validate** — `validate_decision()` is the safety net: it confirms the model id is
   real, the side is valid, the amount is positive, caps buys at available credits and the
   trade cap, caps sells at shares actually held, and **holds on any malformed output**.

So the LLM proposes; deterministic validation disposes. A bad or hallucinated decision can
never produce an invalid trade.

---

## How it runs (two modes)

- **In-process** — `POST /sim/start` / `POST /sim/stop` spin the loops up inside the API
  process. Fine for a light demo.
- **External runner** — [`backend/sim/main.py`](backend/sim/main.py) runs the same loops in
  a **separate process** so poster/investor HTTP traffic and OpenAI calls don't contend
  with the API event loop. Preferred for heavy load. It targets the same public API, so it
  scales horizontally — you can point several runners at one API.

Either way the simulation only uses public endpoints, polls slot availability for
backpressure, and retries transient HTTP failures with backoff.

---

## Why the hybrid matters

A market driven only by math agents is liquid but mechanical; one driven only by LLM
agents is expressive but slow and prone to herding. The hybrid cohort design gives Anex:

- **liquidity and tight markets** from fast math market-makers,
- **trend and mean-reversion** from systematic quants,
- **discretionary, persona-varied flow** from LLM retail and whales,

all reacting to the **same fundamental signal** — judge scores flowing through the ledger
into model fundamentals. The price action you see on the trading floor is the emergent
result of these populations interacting with the orchestration loop.
