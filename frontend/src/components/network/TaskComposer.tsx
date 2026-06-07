"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useUser } from "@/lib/user";
import { useMarket } from "@/lib/market";
import { useBuyCredits } from "@/lib/buyCredits";
import { useNetwork } from "@/lib/networkContext";
import { SUGGESTED_GOALS } from "@/lib/agents";
import { fmtPrice } from "@/lib/format";
import { cn } from "@/lib/cn";
export function TaskComposer() {
  const { userId } = useUser();
  const { portfolio } = useMarket();
  const { addPendingTask, brokerModel, preferredTier } = useNetwork();
  const { openBuyCredits } = useBuyCredits();
  const cash = portfolio?.credits ?? null;
  const [goal, setGoal] = useState("");
  const [budget, setBudget] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [showSuggestions, setShowSuggestions] = useState(false);

  const budgetNum = budget.trim() === "" ? null : Number(budget);
  const budgetInvalid =
    budgetNum !== null &&
    (Number.isNaN(budgetNum) ||
      budgetNum <= 0 ||
      (cash !== null && budgetNum > cash));

  async function submit() {
    const g = goal.trim();
    if (!g || busy || budgetInvalid) return;
    setBusy(true);
    setMsg(null);
    try {
      const res = await api.postTask(
        g,
        userId ?? undefined,
        budgetNum ?? undefined,
        brokerModel,
        preferredTier,
      );
      addPendingTask({
        task_id: res.task_id,
        goal: g,
        budget: res.budget,
        postedAt: new Date().toISOString(),
      });
      setGoal("");
      setShowSuggestions(false);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Failed to post task");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="shrink-0 border-t border-line/60 bg-panel/40 px-4 py-4 backdrop-blur-md">
      <div className="mx-auto flex max-w-3xl flex-col gap-2">
        {showSuggestions && (
          <div className="flex flex-wrap gap-1.5 pb-1">
            {SUGGESTED_GOALS.map((s, i) => (
              <button
                key={i}
                type="button"
                onClick={() => {
                  setGoal(s);
                  setShowSuggestions(false);
                }}
                className="max-w-full truncate rounded-full border border-line/60 bg-base/60 px-3 py-1 text-[11px] text-dim transition-colors hover:border-line-bright hover:text-muted"
                title={s}
              >
                {s.length > 48 ? s.slice(0, 48) + "…" : s}
              </button>
            ))}
          </div>
        )}

        <div className="flex items-end gap-2 rounded-2xl border border-line/80 bg-base/90 p-2 shadow-[0_-4px_24px_-8px_rgba(0,0,0,0.4)] focus-within:border-gold/30">
          <textarea
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            onFocus={() => setShowSuggestions(true)}
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === "Enter") submit();
            }}
            rows={1}
            placeholder="Message the agent network…"
            className="max-h-32 min-h-[40px] flex-1 resize-none bg-transparent px-2 py-2 text-[14px] leading-relaxed text-ink outline-none placeholder:text-faint"
          />
          <button
            type="button"
            onClick={submit}
            disabled={busy || !goal.trim() || budgetInvalid}
            className={cn(
              "mb-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl transition-all",
              goal.trim() && !busy && !budgetInvalid
                ? "bg-gold text-base hover:bg-gold/90"
                : "bg-line text-dim",
            )}
            aria-label="Send"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <path d="M8.5 2.5L14 8l-5.5 5.5V9.5H2V6.5h6.5V2.5z" />
            </svg>
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-3 px-1 font-mono text-[10px] text-dim">
          <label className="flex items-center gap-1.5">
            <span>Budget</span>
            <input
              type="number"
              min={0}
              step="any"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              placeholder={cash !== null ? fmtPrice(cash) : "all"}
              className={cn(
                "w-20 rounded-md border bg-base/60 px-2 py-0.5 text-right text-[10px] tabular text-ink outline-none focus:border-gold/40",
                budgetInvalid ? "border-down" : "border-line/60",
              )}
            />
          </label>
          {budgetInvalid && (
            <span className="flex items-center gap-1.5 text-down">
              over budget
              <button
                type="button"
                onClick={openBuyCredits}
                className="text-gold/80 underline-offset-2 hover:text-gold hover:underline"
              >
                buy credits
              </button>
            </span>
          )}
          {msg && <span className="text-down">{msg}</span>}
        </div>
      </div>
    </div>
  );
}
