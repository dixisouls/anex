"use client";

import { useEffect, useState } from "react";
import { api } from "./api";
import { useFeed } from "./feed";
import type { Agent } from "./types";

export function useAgents() {
  const { subscribe } = useFeed();
  const [agents, setAgents] = useState<Record<string, Agent>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const list = await api.getAgents();
        if (!alive) return;
        const map: Record<string, Agent> = {};
        for (const a of list) map[a.agent_id] = a;
        setAgents(map);
        setError(null);
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : "Failed to load agents");
      } finally {
        if (alive) setLoading(false);
      }
    };
    load();
    const id = setInterval(load, 30_000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  useEffect(() => {
    const unsub = subscribe(
      ["reputation_changed", "credits_changed"],
      (e) => {
        setAgents((prev) => {
          const a = prev[(e as { agent_id: string }).agent_id];
          if (!a) return prev;
          if (e.type === "reputation_changed") {
            return { ...prev, [a.agent_id]: { ...a, reputation: e.new, wins: a.wins } };
          }
          if (e.type === "credits_changed") {
            return { ...prev, [a.agent_id]: { ...a, credits: e.new } };
          }
          return prev;
        });
      },
    );
    return unsub;
  }, [subscribe]);

  return { agents, list: Object.values(agents), loading, error };
}
