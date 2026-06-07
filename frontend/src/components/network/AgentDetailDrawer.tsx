"use client";

import { motion } from "motion/react";
import { agentCategory } from "@/lib/agents";
import { tickerSymbol } from "@/lib/ticker";
import { fmtPrice, fmtNum } from "@/lib/format";
import type { Agent } from "@/lib/types";

export function AgentDetailDrawer({
  agent,
  onClose,
}: {
  agent: Agent;
  onClose: () => void;
}) {
  return (
    <>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        className="fixed inset-0 z-[60] bg-black/60"
      />
      <motion.div
        initial={{ x: "100%" }}
        animate={{ x: 0 }}
        exit={{ x: "100%" }}
        transition={{ type: "spring", stiffness: 320, damping: 34 }}
        className="fixed right-0 top-0 z-[70] flex h-full w-full max-w-md flex-col border-l border-line bg-raised"
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
              <span className="uppercase text-gold">{agent.service_tier}</span>
              {" · "}
              <span className="text-gold">{tickerSymbol(agent.model)}</span> ·{" "}
              {agent.model}
            </div>
          </div>
          <button
            type="button"
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

function DrawerRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between border-b border-line/50 py-1">
      <span className="text-dim">{label}</span>
      <span className="tabular text-ink">{children}</span>
    </div>
  );
}
