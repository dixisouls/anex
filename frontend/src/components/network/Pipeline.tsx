"use client";

import { useMemo, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { useFeed } from "@/lib/feed";
import { buildPipelines, STAGE_ORDER, type Stage, type SubtaskState } from "@/lib/pipeline";
import { fmtPrice, fmtTime } from "@/lib/format";
import { cn } from "@/lib/cn";
import { Markdown } from "@/components/Markdown";
import type { Agent } from "@/lib/types";

const STAGE_LABEL: Record<Stage, string> = {
  posted: "Decomposed",
  ranked: "Auctioned",
  hired: "Hired",
  executed: "Executed",
  scored: "Judged",
};

function scoreColor(s: number) {
  if (s >= 0.7) return "text-up";
  if (s >= 0.4) return "text-gold";
  return "text-down";
}

export function Pipeline({ agents }: { agents: Record<string, Agent> }) {
  const { events } = useFeed();
  const tasks = useMemo(() => buildPipelines(events), [events]);

  if (tasks.length === 0) {
    return (
      <div className="grid h-full place-items-center p-8 text-center">
        <div>
          <div className="font-mono text-sm text-muted">No active tasks</div>
          <div className="mt-1 font-mono text-[11px] text-dim">
            Post a goal above — or hit SIM ▸ Start sim — to watch the agent
            economy work in real time.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 p-3">
      <AnimatePresence initial={false}>
        {tasks.map((t) => {
          const subs = Object.values(t.subtasks).sort((a, b) => a.index - b.index);
          const scored = subs.filter((s) => s.stage === "scored").length;
          return (
            <motion.div
              key={t.task_id}
              layout
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.25 }}
              className="border border-line bg-panel/60"
            >
              <div className="flex items-start justify-between gap-3 border-b border-line px-3 py-2">
                <div className="min-w-0">
                  <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-dim">
                    {fmtTime(t.ts)} · task
                  </div>
                  <div className="mt-0.5 text-sm text-ink">{t.goal}</div>
                </div>
                <span className="shrink-0 font-mono text-[10px] text-dim">
                  {scored}/{subs.length} done
                </span>
              </div>
              <div className="divide-y divide-line/50">
                {subs.map((s, i) => (
                  <SubtaskRow
                    key={s.subtask_id}
                    sub={s}
                    agents={agents}
                    isFinal={i === subs.length - 1}
                  />
                ))}
              </div>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}

function SubtaskRow({
  sub,
  agents,
  isFinal,
}: {
  sub: SubtaskState;
  agents: Record<string, Agent>;
  isFinal: boolean;
}) {
  const curIdx = STAGE_ORDER.indexOf(sub.stage);
  const complete = sub.stage === "scored";
  const agentName = (id?: string) => (id ? agents[id]?.name ?? id : "—");
  const [expanded, setExpanded] = useState(isFinal);

  const maxScore = Math.max(...sub.candidates.map((c) => c.final_score), 0.0001);
  const minScore = Math.min(...sub.candidates.map((c) => c.final_score), 0);

  if (sub.skipped) {
    return (
      <div className="px-3 py-2.5 opacity-70">
        <div className="flex items-start gap-2">
          <span className="mt-px shrink-0 border border-line px-1.5 py-px font-mono text-[9px] text-dim">
            S{sub.index + 1}
          </span>
          <p className="line-clamp-2 flex-1 font-mono text-[11px] text-dim line-through">
            {sub.text || "…"}
          </p>
          <span className="shrink-0 border border-down/40 px-1.5 py-px font-mono text-[9px] uppercase tracking-[0.14em] text-down">
            {sub.skipReason === "budget" ? "Over budget" : "Skipped"}
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="px-3 py-2.5">
      <div className="flex items-start gap-2">
        <span className="mt-px shrink-0 border border-line px-1.5 py-px font-mono text-[9px] text-dim">
          S{sub.index + 1}
        </span>
        <p className="line-clamp-2 flex-1 font-mono text-[11px] text-muted">
          {sub.text || "…"}
        </p>
        {sub.hirePrice != null && (
          <span
            className="shrink-0 font-mono text-[10px] text-gold/80"
            title={
              sub.budgetRemaining != null
                ? `Budget left: ${fmtPrice(sub.budgetRemaining)}`
                : undefined
            }
          >
            −{fmtPrice(sub.hirePrice)}
            {sub.budgetRemaining != null && (
              <span className="ml-1 text-dim">
                · {fmtPrice(sub.budgetRemaining)} left
              </span>
            )}
          </span>
        )}
        {sub.score != null && (
          <span className={cn("shrink-0 font-mono text-xs font-semibold", scoreColor(sub.score))}>
            J {sub.score.toFixed(2)}
          </span>
        )}
      </div>

      {/* Stage rail */}
      <div className="mt-2 flex items-center gap-1">
        {STAGE_ORDER.map((stage, i) => {
          const done = complete || i < curIdx;
          const active = !complete && i === curIdx;
          return (
            <div key={stage} className="flex flex-1 items-center gap-1">
              <div className="flex items-center gap-1.5">
                <span
                  className={cn(
                    "h-1.5 w-1.5 rounded-full",
                    done && "bg-up",
                    active && "bg-gold animate-[pulse-dot_2s_ease-in-out_infinite]",
                    !done && !active && "bg-faint",
                  )}
                />
                <span
                  className={cn(
                    "font-mono text-[9px] uppercase tracking-[0.12em]",
                    done ? "text-up/80" : active ? "text-gold" : "text-faint",
                  )}
                >
                  {STAGE_LABEL[stage]}
                </span>
              </div>
              {i < STAGE_ORDER.length - 1 && (
                <span
                  className={cn(
                    "h-px flex-1",
                    i < curIdx ? "bg-up/40" : "bg-line",
                  )}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Auction candidates */}
      {sub.candidates.length > 0 && (
        <div className="mt-2 flex flex-col gap-1">
          {sub.candidates.slice(0, 3).map((c) => {
            const won = c.agent_id === sub.hiredAgentId;
            const w =
              ((c.final_score - minScore) / (maxScore - minScore || 1)) * 100;
            return (
              <div key={c.agent_id} className="flex items-center gap-2">
                <span
                  className={cn(
                    "w-32 shrink-0 truncate font-mono text-[10px]",
                    won ? "text-gold" : "text-dim",
                  )}
                >
                  {won && "★ "}
                  {agentName(c.agent_id)}
                </span>
                <div className="relative h-2 flex-1 bg-base">
                  <div
                    className={cn("h-full", won ? "bg-gold/70" : "bg-line-bright")}
                    style={{ width: `${Math.max(4, w)}%` }}
                  />
                </div>
                <span className="tabular w-10 text-right font-mono text-[10px] text-muted">
                  {c.final_score.toFixed(2)}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Output */}
      <AnimatePresence>
        {sub.output && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            className="mt-2 overflow-hidden"
          >
            <div className="border-l-2 border-line-bright bg-base/60">
              <button
                type="button"
                onClick={() => setExpanded((v) => !v)}
                className="flex w-full items-center gap-1.5 px-2 py-1.5 text-left transition-colors hover:bg-line/20"
              >
                <span
                  className={cn(
                    "font-mono text-[9px] text-dim transition-transform",
                    expanded && "rotate-90",
                  )}
                >
                  ▸
                </span>
                <span className="flex-1 font-mono text-[9px] uppercase tracking-[0.18em] text-dim">
                  {agentName(sub.hiredAgentId)} output
                  {isFinal && (
                    <span className="ml-1.5 text-gold/70">· final</span>
                  )}
                </span>
                {!expanded && (
                  <span className="font-mono text-[9px] uppercase tracking-[0.16em] text-dim/70">
                    show
                  </span>
                )}
              </button>
              <AnimatePresence initial={false}>
                {expanded && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.2 }}
                    className="overflow-hidden"
                  >
                    <div className="border-t border-line/50 px-2.5 py-2">
                      <Markdown>{sub.output}</Markdown>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
