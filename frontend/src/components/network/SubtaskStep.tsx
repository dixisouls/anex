"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Markdown } from "@/components/Markdown";
import { StepPipeline } from "./StepPipeline";
import { fmtPrice } from "@/lib/format";
import { tickerSymbol } from "@/lib/ticker";
import { cn } from "@/lib/cn";
import type { SubtaskState } from "@/lib/pipeline";
import type { Agent } from "@/lib/types";

function scoreColor(s: number) {
  if (s >= 0.7) return "text-up";
  if (s >= 0.4) return "text-gold";
  return "text-down";
}

export function SubtaskStep({
  sub,
  stepNumber,
  isActive,
  isExpanded,
  onToggle,
  agents,
  hideInlineOutput = false,
}: {
  sub: SubtaskState;
  stepNumber: number;
  isActive: boolean;
  isExpanded: boolean;
  onToggle: () => void;
  agents: Record<string, Agent>;
  hideInlineOutput?: boolean;
}) {
  const [showAuction, setShowAuction] = useState(false);
  const agentName = (id?: string) => (id ? agents[id]?.name ?? id : "—");
  const agentModel = (id?: string) => (id ? agents[id]?.model : undefined);

  const hasOutput = Boolean(sub.output);
  const isDone = sub.stage === "scored";

  const maxScore = Math.max(...sub.candidates.map((c) => c.final_score), 0.0001);
  const minScore = Math.min(...sub.candidates.map((c) => c.final_score), 0);

  if (sub.skipped) {
    return (
      <div className="rounded-xl border border-line/40 bg-panel/20 px-4 py-3 opacity-60">
        <div className="flex items-center gap-2 text-[13px]">
          <span className="font-mono text-[10px] text-dim">Step {stepNumber}</span>
          <span className="flex-1 truncate text-dim line-through">{sub.text}</span>
          <span className="font-mono text-[10px] text-down">
            {sub.skipReason === "budget" ? "Over budget" : "Skipped"}
          </span>
        </div>
      </div>
    );
  }

  return (
    <motion.div
      layout
      className={cn(
        "overflow-hidden rounded-xl border transition-all duration-300",
        isActive
          ? "border-gold/30 bg-panel/90 shadow-[0_4px_24px_-8px_rgba(0,0,0,0.5)]"
          : isDone
            ? "border-line/50 bg-panel/40"
            : "border-line/40 bg-panel/25",
      )}
    >
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-start gap-3 px-4 py-3 text-left"
      >
        <span
          className={cn(
            "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg font-mono text-[11px] font-medium",
            isActive
              ? "bg-gold/15 text-gold"
              : isDone
                ? "bg-up/10 text-up"
                : "bg-base text-dim",
          )}
        >
          {stepNumber}
        </span>
        <div className="min-w-0 flex-1">
          <p
            className={cn(
              "text-[13px] leading-snug text-ink",
              !isExpanded && "line-clamp-1",
            )}
          >
            {sub.text}
          </p>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 font-mono text-[10px]">
            {sub.hiredAgentId && (
              <span className="text-muted">{agentName(sub.hiredAgentId)}</span>
            )}
            {sub.hiredAgentId && agentModel(sub.hiredAgentId) && (
              <span className="text-dim">
                {tickerSymbol(agentModel(sub.hiredAgentId)!)}
              </span>
            )}
            {sub.hirePrice != null && (
              <span className="text-gold/80">−{fmtPrice(sub.hirePrice)}</span>
            )}
            {sub.budgetRemaining != null && (
              <span className="text-up/80">{fmtPrice(sub.budgetRemaining)} left</span>
            )}
            {sub.score != null && (
              <span className={cn("font-semibold", scoreColor(sub.score))}>
                {sub.score.toFixed(2)}
              </span>
            )}
          </div>
        </div>
        <span className="mt-1 shrink-0 text-dim/60">
          <svg
            width="12"
            height="12"
            viewBox="0 0 12 12"
            className={cn(
              "transition-transform duration-200",
              isExpanded && "rotate-180",
            )}
          >
            <path
              d="M3 4.5L6 7.5L9 4.5"
              stroke="currentColor"
              strokeWidth="1.5"
              fill="none"
            />
          </svg>
        </span>
      </button>

      <AnimatePresence initial={false}>
        {isExpanded && (
          <motion.div
            key="body"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.28, ease: [0.4, 0, 0.2, 1] }}
            className="overflow-hidden"
          >
            <div className="border-t border-line/40 px-4 pb-4 pt-1">
              {(isActive || sub.stage !== "posted") && <StepPipeline sub={sub} />}

              {sub.candidates.length > 0 && (
                <div className="mt-3">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setShowAuction((v) => !v);
                    }}
                    className="font-mono text-[9px] uppercase tracking-[0.14em] text-dim hover:text-muted"
                  >
                    {showAuction ? "▾" : "▸"} Auction ({sub.candidates.length})
                  </button>
                  <AnimatePresence>
                    {showAuction && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        className="mt-2 flex flex-col gap-1.5 overflow-hidden"
                      >
                        {sub.candidates.slice(0, 3).map((c) => {
                          const won = c.agent_id === sub.hiredAgentId;
                          const w =
                            ((c.final_score - minScore) /
                              (maxScore - minScore || 1)) *
                            100;
                          return (
                            <div
                              key={c.agent_id}
                              className="flex items-center gap-2"
                            >
                              <span
                                className={cn(
                                  "w-28 shrink-0 truncate font-mono text-[10px]",
                                  won ? "text-gold" : "text-dim",
                                )}
                              >
                                {won && "★ "}
                                {agentName(c.agent_id)}
                              </span>
                              <div className="relative h-1 flex-1 rounded-full bg-base">
                                <div
                                  className={cn(
                                    "h-full rounded-full",
                                    won ? "bg-gold/60" : "bg-line-bright",
                                  )}
                                  style={{ width: `${Math.max(4, w)}%` }}
                                />
                              </div>
                            </div>
                          );
                        })}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              )}

              {hasOutput && !hideInlineOutput && (
                <motion.div
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3, delay: 0.05 }}
                  className="mt-4 border-l-2 border-gold/30 bg-base/80 px-3 py-2"
                >
                  <div className="mb-2 font-mono text-[9px] uppercase tracking-[0.16em] text-dim">
                    {agentName(sub.hiredAgentId)} output
                  </div>
                  <Markdown>{sub.output!}</Markdown>
                </motion.div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
