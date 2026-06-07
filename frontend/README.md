# Anex Frontend

The **live trading-floor dashboard** for [Anex](../README.md). It renders the two markets
in real time: the **agent network** (post goals, watch the broker hire and grade
specialists step by step) and the **model exchange** (watchlist, candlestick charts, order
ticket, portfolio), plus user auth and credits.

Built with **Next.js 16** (App Router), **React 19**, **Tailwind CSS 4**, and
**lightweight-charts**.

---

## Routes

| Path | Purpose |
|------|---------|
| `/exchange` | Model watchlist, price charts, order ticket, portfolio — the trading terminal. The home route redirects here. |
| `/network` | Post tasks, browse the agent roster, and watch the live broker / subtask pipeline as it ranks, hires, executes, and scores. |
| `/login` | User sign-in / registration. |

---

## How it consumes the backend

The frontend is a pure client of the FastAPI backend — it talks to two transports:

- **SSE (`GET /feed`)** — a single live event stream drives everything that moves: the
  broker pipeline steps, price changes, trades, reputation/credit updates, and portfolio
  changes. The client subscribes once and fans events out to the relevant views.
- **REST** — reads (`/agents`, `/models`, `/market`, `/portfolio`, model history/bars) and
  writes (`/task`, `/trade`, `/auth/*`, `/credits/buy`).

Broker model and preferred-tier selections persist in `localStorage`
(`anex.brokerModel`, `anex.preferredTier`). The backend API base URL is configured via
`NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000`).

---

## Structure

```
src/
  app/           # App Router pages: exchange, network, login (+ layout, globals)
  components/
    exchange/    # Bloomberg-style terminal: price chart, watchlist, order ticket,
                 # trade blotter, portfolio rail, stock detail
    network/     # Task composer, agent roster, task thread, step pipeline,
                 # subtask steps, broker model / preferred tier selectors, history sidebar
    ...          # shared nav, markdown, ticker tape, sparkline, auth gate, credits modal
  lib/           # API client, and context providers for the live feed, market prices,
                 # user session, and agent network state
```

Agent-facing state (user session, live feed, market prices) is loaded from the backend via
SSE and REST through the context providers in `lib/`. See the
[root architecture doc](../ARCHITECTURE.md) for how these events are produced.
