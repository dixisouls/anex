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
  EarningsRow,
  FeedEvent,
  ModelStock,
  Portfolio,
  PriceTick,
} from "./types";

export interface SeriesPoint {
  time: number;
  value: number;
  id?: string;
}

interface MarketContextValue {
  models: ModelStock[];
  modelMap: Record<string, ModelStock>;
  history: Record<string, SeriesPoint[]>;
  open: Record<string, number>;
  volume: Record<string, number>;
  portfolio: Portfolio | null;
  earnings: Record<string, EarningsRow[]>;
  loadEarnings: (modelId: string) => void;
  loadHistory: (modelId: string) => void;
  loading: boolean;
  error: string | null;
  refreshAll: () => void;
}

const MarketContext = createContext<MarketContextValue | null>(null);

const POLL_MS = 20_000;
const MAX_POINTS = 400;
const MAX_EARNINGS = 30;
const SPARK_WINDOW = 60;

function tickToPoint(tick: PriceTick, fallbackTime: number): SeriesPoint {
  let time = fallbackTime;
  if (tick.ts) {
    const ms = Date.parse(tick.ts);
    if (!Number.isNaN(ms)) time = Math.floor(ms / 1000);
  }
  return { time, value: tick.price, id: tick.id };
}

/** lightweight-charts requires strictly ascending unique times (seconds). */
export function ensureMonotonicTimes(points: SeriesPoint[]): SeriesPoint[] {
  if (points.length <= 1) return points;
  const out: SeriesPoint[] = [{ ...points[0] }];
  for (let i = 1; i < points.length; i++) {
    const prevTime = out[i - 1]!.time;
    const time = points[i]!.time <= prevTime ? prevTime + 1 : points[i]!.time;
    out.push({ ...points[i]!, time });
  }
  return out;
}

function mergeSeries(
  prev: SeriesPoint[],
  incoming: SeriesPoint[],
  replace: boolean,
): SeriesPoint[] {
  let merged: SeriesPoint[];
  if (replace) {
    merged = incoming.slice(-MAX_POINTS);
  } else {
    const seen = new Set(prev.map((p) => p.id).filter(Boolean));
    merged = [...prev];
    for (const p of incoming) {
      if (p.id && seen.has(p.id)) continue;
      if (p.id) seen.add(p.id);
      merged.push(p);
    }
    if (merged.length > MAX_POINTS) merged = merged.slice(-MAX_POINTS);
  }
  return ensureMonotonicTimes(merged);
}

export function MarketProvider({ children }: { children: ReactNode }) {
  const { subscribe } = useFeed();
  const { userId } = useUser();

  const [modelMap, setModelMap] = useState<Record<string, ModelStock>>({});
  const [history, setHistory] = useState<Record<string, SeriesPoint[]>>({});
  const [open, setOpen] = useState<Record<string, number>>({});
  const [volume, setVolume] = useState<Record<string, number>>({});
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [earnings, setEarnings] = useState<Record<string, EarningsRow[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const timeCursor = useRef<Record<string, number>>({});
  const earningsLoaded = useRef<Set<string>>(new Set());
  const historyLoaded = useRef<Set<string>>(new Set());
  const seenTickIds = useRef<Set<string>>(new Set());

  const loadEarnings = useCallback((modelId: string) => {
    if (earningsLoaded.current.has(modelId)) return;
    earningsLoaded.current.add(modelId);
    api
      .getEarnings(modelId)
      .then((rows) => setEarnings((prev) => ({ ...prev, [modelId]: rows })))
      .catch(() => {
        earningsLoaded.current.delete(modelId);
      });
  }, []);

  const loadHistory = useCallback((modelId: string) => {
    if (historyLoaded.current.has(modelId)) return;
    historyLoaded.current.add(modelId);
    api
      .getModelHistory(modelId, SPARK_WINDOW)
      .then((ticks) => {
        const base = Math.floor(Date.now() / 1000) - ticks.length;
        const points = ticks.map((t, i) => tickToPoint(t, base + i));
        for (const p of points) {
          if (p.id) seenTickIds.current.add(p.id);
        }
        setHistory((prev) => ({
          ...prev,
          [modelId]: mergeSeries(prev[modelId] ?? [], points, true),
        }));
        if (points.length > 0) {
          timeCursor.current[modelId] = points[points.length - 1].time;
        }
      })
      .catch(() => {
        historyLoaded.current.delete(modelId);
      });
  }, []);

  const appendPoint = useCallback(
    (modelId: string, value: number, tickId?: string) => {
      if (tickId && seenTickIds.current.has(tickId)) return;
      if (tickId) seenTickIds.current.add(tickId);
      setHistory((prev) => {
        const series = prev[modelId] ?? [];
        const last = timeCursor.current[modelId] ?? Math.floor(Date.now() / 1000);
        const t = Math.max(last + 1, Math.floor(Date.now() / 1000));
        timeCursor.current[modelId] = t;
        const next = ensureMonotonicTimes([
          ...series,
          { time: t, value, id: tickId },
        ]);
        return {
          ...prev,
          [modelId]: next.length > MAX_POINTS ? next.slice(-MAX_POINTS) : next,
        };
      });
    },
    [],
  );

  const hydrate = useCallback(async () => {
    try {
      const market = await api.getMarket();
      const map: Record<string, ModelStock> = {};
      const opens: Record<string, number> = {};
      const vols: Record<string, number> = {};
      for (const m of market.models) {
        map[m.model_id] = m;
        if (m.session_open != null) opens[m.model_id] = m.session_open;
        if (m.volume != null) vols[m.model_id] = m.volume;
      }
      setModelMap(map);
      setOpen(opens);
      setVolume((prev) => ({ ...prev, ...vols }));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load market");
    } finally {
      setLoading(false);
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
    refreshPortfolio();
  }, [hydrate, refreshPortfolio]);

  useEffect(() => {
    hydrate();
    const id = setInterval(hydrate, POLL_MS);
    return () => clearInterval(id);
  }, [hydrate]);

  useEffect(() => {
    refreshPortfolio();
  }, [refreshPortfolio]);

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
          appendPoint(e.model_id, e.new, e.event_id);
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
          // price_changed follows trades and carries the pool tick.
        } else if (e.type === "earnings_injected") {
          const row: EarningsRow = {
            event_id: e.event_id,
            ts: e.ts,
            agent_id: e.agent_id,
            amount: e.amount,
            judge_score: e.judge_score,
          };
          setEarnings((prev) => {
            const list = prev[e.model_id] ?? [];
            return {
              ...prev,
              [e.model_id]: [row, ...list].slice(0, MAX_EARNINGS),
            };
          });
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
        earnings,
        loadEarnings,
        loadHistory,
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

export function sparkWindow(values: number[], window = SPARK_WINDOW): number[] {
  return values.slice(-window);
}

export function sparkSlopePositive(values: number[]): boolean {
  if (values.length < 2) return true;
  return values[values.length - 1] >= values[0];
}
