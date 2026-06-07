"use client";

import { useMemo, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { agentCategory, CATEGORIES, type Category } from "@/lib/agents";
import { tickerSymbol } from "@/lib/ticker";
import { fmtPrice, fmtNum } from "@/lib/format";
import { cn } from "@/lib/cn";
import type { Agent } from "@/lib/types";

export function AgentRoster({
  list,
  loading,
}: {
  list: Agent[];
  loading: boolean;
}) {
  const [cat, setCat] = useState<Category | "All">("All");
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<Agent | null>(null);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return list
      .filter((a) => (cat === "All" ? true : agentCategory(a.agent_id) === cat))
      .filter(
        (a) =>
          !needle ||
          a.name.toLowerCase().includes(needle) ||
          a.skills.some((s) => s.toLowerCase().includes(needle)),
      )
      .sort((a, b) => b.reputation - a.reputation);
  }, [list, cat, q]);

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b border-line p-3">
        <div className="flex flex-wrap gap-1">
          {(["All", ...CATEGORIES] as const).map((c) => (
            <button
              key={c}
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
          placeholder="search skills…"
          className="ml-auto w-40 border border-line bg-base px-2 py-1 font-mono text-[11px] text-ink outline-none placeholder:text-faint focus:border-gold-dim"
        />
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {loading && list.length === 0 ? (
          <div className="grid grid-cols-2 gap-2 lg:grid-cols-3">
            {Array.from({ length: 9 }).map((_, i) => (
              <div key={i} className="h-28 animate-pulse bg-panel/60" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-2 lg:grid-cols-3 2xl:grid-cols-4">
            {filtered.map((a) => (
              <AgentCard key={a.agent_id} agent={a} onClick={() => setOpen(a)} />
            ))}
          </div>
        )}
      </div>

      <AnimatePresence>
        {open && <AgentDrawer agent={open} onClose={() => setOpen(null)} />}
      </AnimatePresence>
    </div>
  );
}

function RepBar({ value }: { value: number }) {
  return (
    <div className="h-1 w-full bg-base">
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

function AgentCard({ agent, onClick }: { agent: Agent; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="flex flex-col gap-2 border border-line bg-panel/60 p-2.5 text-left transition-colors hover:border-line-bright hover:bg-panel"
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-semibold text-ink">{agent.name}</span>
        <span className="shrink-0 font-mono text-[9px] uppercase tracking-[0.12em] text-dim">
          {agentCategory(agent.agent_id)}
        </span>
      </div>
      <div className="flex items-center gap-2 font-mono text-[10px] text-muted">
        <span className="border border-line px-1 text-gold">
          {tickerSymbol(agent.model)}
        </span>
        <span>{fmtPrice(agent.price ?? 0)}/hire</span>
      </div>
      <RepBar value={agent.reputation} />
      <div className="flex items-center justify-between font-mono text-[10px] text-dim">
        <span>rep {agent.reputation.toFixed(2)}</span>
        <span>
          {agent.hires}h · {agent.wins}w
        </span>
      </div>
    </button>
  );
}

function AgentDrawer({ agent, onClose }: { agent: Agent; onClose: () => void }) {
  return (
    <>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        className="fixed inset-0 z-40 bg-black/60"
      />
      <motion.div
        initial={{ x: "100%" }}
        animate={{ x: 0 }}
        exit={{ x: "100%" }}
        transition={{ type: "spring", stiffness: 320, damping: 34 }}
        className="fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col border-l border-line bg-raised"
      >
        <div className="flex items-start justify-between border-b border-line p-4">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold text-ink">{agent.name}</h2>
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-dim">
                {agentCategory(agent.agent_id)}
              </span>
            </div>
            <div className="mt-1 font-mono text-[11px] text-muted">
              <span className="text-gold">{tickerSymbol(agent.model)}</span> ·{" "}
              {agent.model}
            </div>
          </div>
          <button
            onClick={onClose}
            className="border border-line px-2 py-1 font-mono text-xs text-dim hover:text-ink"
          >
            ✕
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          <div className="grid grid-cols-4 gap-px bg-line">
            <DrawerStat label="Rep" value={agent.reputation.toFixed(2)} />
            <DrawerStat label="Hire" value={fmtPrice(agent.price ?? 0)} />
            <DrawerStat label="Hires" value={fmtNum(agent.hires)} />
            <DrawerStat label="Wins" value={fmtNum(agent.wins)} />
          </div>

          <h3 className="mt-4 font-mono text-[9px] uppercase tracking-[0.2em] text-dim">
            Capability
          </h3>
          <p className="mt-1 text-sm leading-relaxed text-muted">
            {agent.capability_text}
          </p>

          <h3 className="mt-4 font-mono text-[9px] uppercase tracking-[0.2em] text-dim">
            Skills
          </h3>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {agent.skills.map((s) => (
              <span
                key={s}
                className="border border-line px-2 py-0.5 font-mono text-[10px] text-muted"
              >
                {s}
              </span>
            ))}
          </div>

          <h3 className="mt-4 font-mono text-[9px] uppercase tracking-[0.2em] text-dim">
            Economics
          </h3>
          <div className="mt-1.5 flex flex-col gap-1 font-mono text-[11px]">
            <DrawerRow label="Margin">
              {(agent.margin * 100).toFixed(0)}%
            </DrawerRow>
            <DrawerRow label="Treasury credits">
              {fmtPrice(agent.credits)}
            </DrawerRow>
            <DrawerRow label="Runs on model">{agent.model}</DrawerRow>
          </div>
        </div>
      </motion.div>
    </>
  );
}

function DrawerStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-raised p-2 text-center">
      <div className="font-mono text-[9px] uppercase tracking-[0.16em] text-dim">
        {label}
      </div>
      <div className="tabular font-mono text-sm text-ink">{value}</div>
    </div>
  );
}

function DrawerRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b border-line/50 py-1">
      <span className="text-dim">{label}</span>
      <span className="tabular text-ink">{children}</span>
    </div>
  );
}
