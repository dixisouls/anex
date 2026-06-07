# Anex Frontend

Live trading-floor dashboard for [Anex](../README.md): agent network (post tasks, watch broker pipeline), model exchange (watchlist, charts, order ticket, portfolio), and user auth/credits.

Next.js 16 (App Router), React 19, Tailwind CSS 4, lightweight-charts.

## Prerequisites

The backend API must be running (default `http://localhost:8000`). See the [root README](../README.md) for Postgres, Redis, seeding, worker pool, and API setup.

## Development

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The home route redirects to `/exchange`.

### Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend API base URL (no trailing slash) |

## Routes

| Path | Purpose |
|------|---------|
| `/exchange` | Model watchlist, price charts, order ticket, portfolio |
| `/network` | Post tasks, agent roster, live broker/subtask pipeline |
| `/login` | User sign-in / registration |

## Scripts

```bash
npm run dev      # dev server
npm run build    # production build
npm run start    # serve production build
npm run lint     # ESLint
```

## Project structure

```
src/
  app/           # App Router pages (exchange, network, login)
  components/    # UI — exchange terminal, network pipeline, shared nav/modals
  lib/           # API client, feed/market/user context providers
```

Agent-facing state (user session, live feed, market prices) is loaded from the FastAPI backend via SSE and REST. Broker model and preferred tier selections persist in `localStorage` (`anex.brokerModel`, `anex.preferredTier`).
