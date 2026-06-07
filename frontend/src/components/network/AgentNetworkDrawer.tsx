"use client";

import { useMemo, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { CATEGORIES, type Category } from "@/lib/agents";
import { groupAgentsByCapability } from "@/lib/groupAgents";
import { tickerSymbol } from "@/lib/ticker";
import { fmtPrice } from "@/lib/format";
import { cn } from "@/lib/cn";
import { useNetwork } from "@/lib/networkContext";
import { AgentDetailDrawer } from "./AgentDetailDrawer";
import type { Agent } from "@/lib/types";

function RepBar({ value }: { value: number }) {
  return (
    <div className="h-1 w-16 bg-base">
      <div
        className={cn(
          "h-full",
          value >= 0.7 ? "bg-up" : value >= 0.45 ? "bg-gold" : "bg-down",
        )}
        style={{ width: `${Math.min(100, value * 100)}%` }}
      />
    </div>
  );
}

export function AgentNetworkDrawer({
  list,
  loading,
}: {
  list: Agent[];
  loading: boolean;
}) {
  const { agentsOpen, setAgentsOpen } = useNetwork();
  const [cat, setCat] = useState<Category | "All">("All");
  const [q, setQ] = useState("");
  const [detail, setDetail] = useState<Agent | null>(null);

  const groups = useMemo(() => groupAgentsByCapability(list), [list]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return groups.filter((g) => {
      if (cat !== "All" && g.category !== cat) return false;
      if (!needle) return true;
      return (
        g.name.toLowerCase().includes(needle) ||
        g.capability_id.toLowerCase().includes(needle) ||
        g.variants.some(
          (v) =>
            v.model.toLowerCase().includes(needle) ||
            v.skills.some((s) => s.toLowerCase().includes(needle)),
        )
      );
    });
  }, [groups, cat, q]);

  return (
    <AnimatePresence>
      {agentsOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setAgentsOpen(false)}
            className="fixed inset-0 z-40 bg-black/50 backdrop-blur-[2px]"
          />
          <motion.aside
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 320, damping: 34 }}
            className="fixed right-0 top-0 z-50 flex h-full w-full max-w-lg flex-col border-l border-line bg-raised"
          >
            <div className="flex items-center justify-between border-b border-line px-4 py-3">
              <div>
                <h2 className="font-mono text-xs font-semibold uppercase tracking-[0.2em] text-ink">
                  Agent network
                </h2>
                <p className="mt-0.5 font-mono text-[10px] text-dim">
                  {groups.length} capabilities · {list.length} tier variants
                </p>
              </div>
              <button
                type="button"
                onClick={() => setAgentsOpen(false)}
                className="border border-line px-2 py-1 font-mono text-xs text-dim hover:text-ink"
              >
                ✕
              </button>
            </div>

            <div className="flex flex-wrap items-center gap-2 border-b border-line p-3">
              <div className="flex flex-wrap gap-1">
                {(["All", ...CATEGORIES] as const).map((c) => (
                  <button
                    key={c}
                    type="button"
                    onClick={() => setCat(c)}
                    className={cn(
                      "border px-2 py-1 font-mono text-[10px] uppercase tracking-[0.14em] transition-colors",
                      cat === c
                        ? "border-gold-dim text-gold"
                        : "border-line text-dim hover:text-muted",
                    )}
                  >
                    {c}
                  </button>
                ))}
              </div>
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search…"
                className="ml-auto w-full border border-line bg-base px-2 py-1 font-mono text-[11px] text-ink outline-none placeholder:text-faint focus:border-gold-dim sm:w-44"
              />
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto p-3">
              {loading && list.length === 0 ? (
                <div className="flex flex-col gap-2">
                  {Array.from({ length: 8 }).map((_, i) => (
                    <div key={i} className="h-20 animate-pulse bg-panel/60" />
                  ))}
                </div>
              ) : (
                <div className="flex flex-col gap-2">
                  {filtered.map((g) => (
                    <CapabilityCard
                      key={g.capability_id}
                      group={g}
                      onSelect={setDetail}
                    />
                  ))}
                </div>
              )}
            </div>
          </motion.aside>

          <AnimatePresence>
            {detail && (
              <AgentDetailDrawer
                agent={detail}
                onClose={() => setDetail(null)}
              />
            )}
          </AnimatePresence>
        </>
      )}
    </AnimatePresence>
  );
}

function CapabilityCard({
  group,
  onSelect,
}: {
  group: ReturnType<typeof groupAgentsByCapability>[number];
  onSelect: (a: Agent) => void;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="border border-line bg-panel/50">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-2.5 text-left hover:bg-panel/80"
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-ink">{group.name}</span>
            <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-dim">
              {group.category}
            </span>
          </div>
          <div className="mt-0.5 font-mono text-[10px] text-dim">
            {group.variants.length} tier
            {group.variants.length === 1 ? "" : "s"} · best rep{" "}
            {group.bestReputation.toFixed(2)}
          </div>
        </div>
        <span className="font-mono text-[9px] text-dim">{open ? "▾" : "▸"}</span>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden border-t border-line/50"
          >
            {group.variants.map((v) => (
              <button
                key={v.agent_id}
                type="button"
                onClick={() => onSelect(v)}
                className="flex w-full items-center gap-3 border-b border-line/30 px-3 py-2 text-left font-mono text-[10px] transition-colors last:border-0 hover:bg-base/60"
              >
                <span className="w-12 shrink-0 uppercase tracking-[0.12em] text-gold">
                  {v.service_tier}
                </span>
                <span className="shrink-0 border border-line px-1 text-muted">
                  {tickerSymbol(v.model)}
                </span>
                <RepBar value={v.reputation} />
                <span className="tabular text-muted">
                  {v.reputation.toFixed(2)}
                </span>
                <span className="ml-auto text-dim">
                  {fmtPrice(v.price ?? 0)}
                </span>
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
