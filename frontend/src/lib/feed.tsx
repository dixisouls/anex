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
import { API_BASE } from "./api";
import type { FeedEvent, FeedEventType } from "./types";

const ALL_EVENT_TYPES: FeedEventType[] = [
  "task_posted",
  "candidates_ranked",
  "agent_hired",
  "subtask_skipped",
  "task_executed",
  "task_scored",
  "reputation_changed",
  "credits_changed",
  "model_listed",
  "price_changed",
  "earnings_injected",
  "trade_executed",
  "portfolio_changed",
];

const TASK_EVENT_TYPES: Set<FeedEventType> = new Set([
  "task_posted",
  "candidates_ranked",
  "agent_hired",
  "subtask_skipped",
  "task_executed",
  "task_scored",
]);

export type FeedStatus = "connecting" | "open" | "closed";

type Listener = (e: FeedEvent) => void;

interface Subscription {
  types: Set<FeedEventType> | null;
  fn: Listener;
}

interface FeedContextValue {
  status: FeedStatus;
  events: FeedEvent[];
  taskEvents: FeedEvent[];
  subscribe: (
    types: FeedEventType | FeedEventType[] | null,
    fn: Listener,
  ) => () => void;
}

const FeedContext = createContext<FeedContextValue | null>(null);

const MAX_LOG = 250;
const MAX_TASK_LOG = 500;

export function FeedProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<FeedStatus>("connecting");
  const [events, setEvents] = useState<FeedEvent[]>([]);
  const [taskEvents, setTaskEvents] = useState<FeedEvent[]>([]);
  const listeners = useRef<Set<Subscription>>(new Set());

  useEffect(() => {
    const es = new EventSource(`${API_BASE}/feed`);

    const handle = (ev: MessageEvent) => {
      let data: FeedEvent;
      try {
        data = JSON.parse(ev.data) as FeedEvent;
      } catch {
        return;
      }
      if (TASK_EVENT_TYPES.has(data.type)) {
        setTaskEvents((prev) => {
          const filtered = prev.filter((e) => e.event_id !== data.event_id);
          const next = [data, ...filtered];
          return next.length > MAX_TASK_LOG ? next.slice(0, MAX_TASK_LOG) : next;
        });
      } else {
        setEvents((prev) => {
          const next = [data, ...prev];
          return next.length > MAX_LOG ? next.slice(0, MAX_LOG) : next;
        });
      }
      for (const sub of listeners.current) {
        if (sub.types === null || sub.types.has(data.type)) {
          try {
            sub.fn(data);
          } catch {
            /* listener errors are isolated */
          }
        }
      }
    };

    for (const t of ALL_EVENT_TYPES) es.addEventListener(t, handle as EventListener);

    es.onopen = () => setStatus("open");
    es.onerror = () => setStatus("connecting");

    return () => {
      es.close();
      setStatus("closed");
    };
  }, []);

  const subscribe = useCallbackShim(listeners);

  return (
    <FeedContext.Provider value={{ status, events, taskEvents, subscribe }}>
      {children}
    </FeedContext.Provider>
  );
}

// Stable subscribe function bound to the listener registry.
function useCallbackShim(listeners: React.RefObject<Set<Subscription>>) {
  const ref = useRef<FeedContextValue["subscribe"]>(null);
  if (ref.current === null) {
    ref.current = (types, fn) => {
      const set =
        types === null
          ? null
          : new Set(Array.isArray(types) ? types : [types]);
      const sub: Subscription = { types: set, fn };
      listeners.current.add(sub);
      return () => {
        listeners.current.delete(sub);
      };
    };
  }
  return ref.current;
}

export function useFeed(): FeedContextValue {
  const ctx = useContext(FeedContext);
  if (!ctx) throw new Error("useFeed must be used within FeedProvider");
  return ctx;
}

/** Subscribe to feed events of given type(s) with a stable callback. */
export function useFeedEvent(
  types: FeedEventType | FeedEventType[] | null,
  fn: Listener,
) {
  const { subscribe } = useFeed();
  const fnRef = useRef(fn);
  fnRef.current = fn;

  useEffect(() => {
    const unsub = subscribe(types, (e) => fnRef.current(e));
    return unsub;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subscribe, Array.isArray(types) ? types.join(",") : types]);
}
