"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "motion/react";
import { AgentChatMessage } from "./AgentChatMessage";
import { SubtaskStep } from "./SubtaskStep";
import { fmtTime, fmtPrice } from "@/lib/format";
import { useNetwork } from "@/lib/networkContext";
import {
  activeSubtaskIndex,
  isTaskComplete,
  sortedSubtasks,
  taskPhase,
  taskSpendSummary,
  type TaskState,
} from "@/lib/pipeline";
import type { PendingTask } from "@/lib/taskThread";
import type { Agent } from "@/lib/types";

export function TaskBlock({
  view,
  agents,
}: {
  view: { kind: "pending"; task: PendingTask } | { kind: "live"; task: TaskState };
  agents: Record<string, Agent>;
}) {
  const { taskBudgets } = useNetwork();
  const isPending = view.kind === "pending";
  const taskId = isPending ? view.task.task_id : view.task.task_id;
  const goal = isPending ? view.task.goal : view.task.goal;
  const ts = isPending ? view.task.postedAt : view.task.ts;
  const budget = isPending ? view.task.budget : taskBudgets[taskId];
  const liveTask = view.kind === "live" ? view.task : null;
  const subs = liveTask ? sortedSubtasks(liveTask) : [];
  const phase = taskPhase(liveTask, isPending);
  const activeIdx = subs.length ? activeSubtaskIndex(subs) : 0;
  const complete = liveTask ? isTaskComplete(subs) : false;

  const [pinnedOpen, setPinnedOpen] = useState<Set<string>>(new Set());
  const prevActiveIdx = useRef(activeIdx);

  // When focus moves to a new step, collapse the previous unless user pinned it
  useEffect(() => {
    if (prevActiveIdx.current !== activeIdx) {
      setPinnedOpen((prev) => {
        const next = new Set(prev);
        const prevSub = subs[prevActiveIdx.current];
        if (prevSub && next.has(prevSub.subtask_id)) {
          next.delete(prevSub.subtask_id);
        }
        return next;
      });
      prevActiveIdx.current = activeIdx;
    }
  }, [activeIdx, subs]);

  const isStepExpanded = (subtaskId: string, index: number) => {
    if (index === activeIdx && !complete) return true;
    if (pinnedOpen.has(subtaskId)) return true;
    return false;
  };

  const toggleStep = (subtaskId: string, index: number) => {
    if (index === activeIdx && !complete) return;
    setPinnedOpen((prev) => {
      const next = new Set(prev);
      if (next.has(subtaskId)) next.delete(subtaskId);
      else next.add(subtaskId);
      return next;
    });
  };

  const lastSub = subs.length > 0 ? subs[subs.length - 1] : null;
  const finalOutput =
    lastSub?.output && !lastSub.skipped ? lastSub.output : null;
  const { totalCharged, finalRemaining } = taskSpendSummary(subs);

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32, ease: [0.4, 0, 0.2, 1] }}
      className="flex flex-col gap-4"
    >
      {/* User message */}
      <div className="flex justify-end pl-8">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-raised px-4 py-3 shadow-sm">
          <p className="text-[14px] leading-relaxed text-ink">{goal}</p>
          <div className="mt-1.5 flex flex-wrap gap-2 font-mono text-[10px] text-dim">
            <span>{fmtTime(ts)}</span>
            {budget != null && <span>· {fmtPrice(budget)} budget</span>}
          </div>
        </div>
      </div>

      {/* Left-aligned system notes */}
      <div className="flex flex-col gap-1 pr-12">
        <p className="font-mono text-[11px] text-dim">
          Posted · {fmtTime(ts)}
        </p>
        {phase === "decomposing" && (
          <p className="font-mono text-[11px] text-muted">
            Broker decomposing…
          </p>
        )}
        {subs.length > 0 && phase !== "decomposing" && (
          <p className="font-mono text-[11px] text-muted">
            Split into {subs.length} step{subs.length === 1 ? "" : "s"}
          </p>
        )}
      </div>

      {/* Agent steps — left aligned */}
      {subs.length > 0 && (
        <motion.div
          initial="hidden"
          animate="show"
          variants={{
            hidden: {},
            show: { transition: { staggerChildren: 0.06 } },
          }}
          className="flex flex-col gap-2.5 pr-4"
        >
          {subs.map((sub, i) => (
            <motion.div
              key={sub.subtask_id}
              variants={{
                hidden: { opacity: 0, y: 6 },
                show: { opacity: 1, y: 0 },
              }}
            >
              <SubtaskStep
                sub={sub}
                stepNumber={i + 1}
                isActive={!complete && i === activeIdx}
                isExpanded={isStepExpanded(sub.subtask_id, i)}
                onToggle={() => toggleStep(sub.subtask_id, i)}
                agents={agents}
                hideInlineOutput={i === subs.length - 1}
              />
            </motion.div>
          ))}
        </motion.div>
      )}

      {finalOutput && <AgentChatMessage content={finalOutput} />}

      {complete && (
        <div className="flex flex-col gap-1">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-up/70">
            Task complete
          </p>
          {(totalCharged > 0 || finalRemaining != null) && (
            <p className="font-mono text-[10px] text-muted">
              {totalCharged > 0 && (
                <span className="text-gold/80">
                  Total charged −{fmtPrice(totalCharged)}
                </span>
              )}
              {totalCharged > 0 && finalRemaining != null && (
                <span className="text-dim"> · </span>
              )}
              {finalRemaining != null && (
                <span className="text-up/80">
                  {fmtPrice(finalRemaining)} remaining
                </span>
              )}
            </p>
          )}
        </div>
      )}
    </motion.article>
  );
}
