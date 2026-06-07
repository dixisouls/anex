"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useUser } from "@/lib/user";
import { SUGGESTED_GOALS } from "@/lib/agents";
import { cn } from "@/lib/cn";
import type { TaskSlots } from "@/lib/types";

export function TaskComposer() {
  const { userId } = useUser();
  const [goal, setGoal] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [slots, setSlots] = useState<TaskSlots | null>(null);

  useEffect(() => {
    let alive = true;
    const poll = async () => {
      try {
        const s = await api.getTaskSlots();
        if (alive) setSlots(s);
      } catch {
        /* ignore */
      }
    };
    poll();
    const id = setInterval(poll, 4000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  async function submit() {
    const g = goal.trim();
    if (!g || busy) return;
    setBusy(true);
    setMsg(null);
    try {
      await api.postTask(g, userId ?? undefined);
      setMsg("Task posted — watch the pipeline below.");
      setGoal("");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Failed to post task");
    } finally {
      setBusy(false);
    }
  }

  const full = slots ? slots.available <= 0 : false;

  return (
    <div className="flex flex-col gap-3 p-3">
      <textarea
        value={goal}
        onChange={(e) => setGoal(e.target.value)}
        onKeyDown={(e) => {
          if ((e.metaKey || e.ctrlKey) && e.key === "Enter") submit();
        }}
        rows={3}
        placeholder="Describe a goal. The broker will decompose it, auction each subtask to the agent network, and execute it live…"
        className="resize-none border border-line bg-base px-3 py-2 font-mono text-sm text-ink outline-none placeholder:text-faint focus:border-gold-dim"
      />

      <div className="flex flex-wrap gap-1.5">
        {SUGGESTED_GOALS.map((s, i) => (
          <button
            key={i}
            onClick={() => setGoal(s)}
            className="max-w-full truncate border border-line px-2 py-1 font-mono text-[10px] text-dim transition-colors hover:border-line-bright hover:text-muted"
            title={s}
          >
            {s.length > 46 ? s.slice(0, 46) + "…" : s}
          </button>
        ))}
      </div>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 font-mono text-[10px] text-dim">
          {slots && (
            <>
              <span
                className={cn(
                  "inline-block h-1.5 w-1.5 rounded-full",
                  full ? "bg-down" : "bg-up",
                )}
              />
              <span>
                {slots.available}/{slots.max} broker slots
              </span>
            </>
          )}
          {msg && <span className="text-muted">· {msg}</span>}
        </div>
        <button
          onClick={submit}
          disabled={busy || !goal.trim()}
          className="bg-gold/20 px-4 py-2 font-mono text-xs font-semibold uppercase tracking-[0.2em] text-gold transition-colors hover:bg-gold/30 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy ? "Posting…" : "Post task ⌘↵"}
        </button>
      </div>
    </div>
  );
}
