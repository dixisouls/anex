"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { api } from "./api";
import { useFeed } from "./feed";
import { useUser } from "./user";
import type {
  FeedEvent,
  ModelStock,
  Portfolio,
  UserPublic,
} from "./types";

export interface SeriesPoint {
  time: number;
  value: number;
}

interface MarketContextValue {
  models: ModelStock[];
  modelMap: Record<string, ModelStock>;
  history: Record<string, SeriesPoint[]>;
  open: Record<string, number>;
  volume: Record<string, number>;
  portfolio: Portfolio | null;
  leaderboard: UserPublic[];
  loading: boolean;
  error: string | null;
  refreshAll: () => void;
}

const MarketContext = createContext<MarketContextValue | null>(null);

const POLL_MS = 20_000;
const MAX_POINTS = 400;

export function MarketProvider({ children }: { children: ReactNode }) {
  const { subscribe } = useFeed();
  const { userId } = useUser();

  const [modelMap, setModelMap] = useState<Record<string, ModelStock>>({});
  const [history, setHistory] = useState<Record<string, SeriesPoint[]>>({});
  const [open, setOpen] = useState<Record<string, number>>({});
  const [volume, setVolume] = useState<Record<string, number>>({});
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [leaderboard, setLeaderboard] = useState<UserPublic[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const timeCursor = useRef<Record<string, number>>({});

  const appendPoint = useCallback((modelId: string, value: number) => {
    setHistory((prev) => {
      const series = prev[modelId] ?? [];
      const last = timeCursor.current[modelId] ?? Math.floor(Date.now() / 1000);
      const t = Math.max(last + 1, Math.floor(Date.now() / 1000));
      timeCursor.current[modelId] = t;
      const next = [...series, { time: t, value }];
      return {
        ...prev,
        [modelId]: next.length > MAX_POINTS ? next.slice(-MAX_POINTS) : next,
      };
    });
  }, []);

  const hydrate = useCallback(async () => {
    try {
      const market = await api.getMarket();
      const map: Record<string, ModelStock> = {};
      for (const m of market.models) map[m.model_id] = m;
      setModelMap(map);
      setError(null);

      // Seed history from the price stream (synthetic monotonic timestamps).
      setHistory((prev) => {
        const next = { ...prev };
        const base = Math.floor(Date.now() / 1000) - market.history.length;
        const counter: Record<string, number> = {};
        for (const m of market.models) {
          if (!next[m.model_id]) {
            counter[m.model_id] = 0;
            next[m.model_id] = [];
          }
        }
        let i = 0;
        for (const tick of market.history) {
          if (!next[tick.model_id]) {
            next[tick.model_id] = [];
            counter[tick.model_id] = 0;
          }
          if (counter[tick.model_id] === undefined) continue;
          next[tick.model_id].push({ time: base + i, value: tick.price });
          i += 1;
        }
        // Ensure every model has at least one point (its current price).
        for (const m of market.models) {
          if (!next[m.model_id] || next[m.model_id].length === 0) {
            next[m.model_id] = [{ time: base + i, value: m.price }];
            i += 1;
          }
          const arr = next[m.model_id];
          timeCursor.current[m.model_id] = arr[arr.length - 1].time;
        }
        return next;
      });

      setOpen((prev) => {
        const next = { ...prev };
        for (const m of market.models) {
          if (next[m.model_id] === undefined) {
            const series = market.history.filter((h) => h.model_id === m.model_id);
            next[m.model_id] = series.length ? series[0].price : m.price;
          }
        }
        return next;
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load market");
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshLeaderboard = useCallback(async () => {
    try {
      setLeaderboard(await api.getUsers());
    } catch {
      /* non-critical */
    }
  }, []);

  const refreshPortfolio = useCallback(async () => {
    if (!userId) return;
    try {
      setPortfolio(await api.getPortfolio(userId));
    } catch {
      /* non-critical */
    }
  }, [userId]);

  const refreshAll = useCallback(() => {
    hydrate();
    refreshLeaderboard();
    refreshPortfolio();
  }, [hydrate, refreshLeaderboard, refreshPortfolio]);

  // Initial load + polling reconciliation.
  useEffect(() => {
    hydrate();
    refreshLeaderboard();
    const id = setInterval(() => {
      hydrate();
      refreshLeaderboard();
    }, POLL_MS);
    return () => clearInterval(id);
  }, [hydrate, refreshLeaderboard]);

  useEffect(() => {
    refreshPortfolio();
  }, [refreshPortfolio]);

  // Live patching from the SSE feed.
  useEffect(() => {
    const unsub = subscribe(
      ["price_changed", "trade_executed", "earnings_injected", "portfolio_changed"],
      (e: FeedEvent) => {
        if (e.type === "price_changed") {
          setModelMap((prev) =>
            prev[e.model_id]
              ? { ...prev, [e.model_id]: { ...prev[e.model_id], price: e.new } }
              : prev,
          );
          setOpen((prev) =>
            prev[e.model_id] === undefined
              ? { ...prev, [e.model_id]: e.old }
              : prev,
          );
          appendPoint(e.model_id, e.new);
        } else if (e.type === "trade_executed") {
          setVolume((prev) => ({
            ...prev,
            [e.model_id]: (prev[e.model_id] ?? 0) + Math.abs(e.shares),
          }));
          setModelMap((prev) =>
            prev[e.model_id]
              ? { ...prev, [e.model_id]: { ...prev[e.model_id], price: e.price } }
              : prev,
          );
        } else if (e.type === "portfolio_changed") {
          if (e.user_id === userId) {
            setPortfolio((prev) =>
              prev
                ? {
                    ...prev,
                    credits: e.credits,
                    holdings_value: e.holdings_value,
                    total: e.total,
                  }
                : prev,
            );
            refreshPortfolio();
          }
        }
      },
    );
    return unsub;
  }, [subscribe, appendPoint, userId, refreshPortfolio]);

  const models = Object.values(modelMap).sort((a, b) => b.price - a.price);

  return (
    <MarketContext.Provider
      value={{
        models,
        modelMap,
        history,
        open,
        volume,
        portfolio,
        leaderboard,
        loading,
        error,
        refreshAll,
      }}
    >
      {children}
    </MarketContext.Provider>
  );
}

export function useMarket(): MarketContextValue {
  const ctx = useContext(MarketContext);
  if (!ctx) throw new Error("useMarket must be used within MarketProvider");
  return ctx;
}

export function changePct(price: number, open: number | undefined): number {
  if (!open || open === 0) return 0;
  return ((price - open) / open) * 100;
}
