"use client";

import { useMemo } from "react";
import { useFeed } from "@/lib/feed";
import { useNetwork } from "@/lib/networkContext";
import { buildPipelines, isTaskComplete, sortedSubtasks, taskPhase } from "@/lib/pipeline";
import {
  mergedTaskList,
  pickDefaultTaskId,
  type TaskView,
} from "@/lib/taskThread";
import { fmtTime } from "@/lib/format";
import { cn } from "@/lib/cn";

function statusLabel(view: TaskView): string {
  if (view.kind === "pending") return "posting";
  const phase = taskPhase(view.task, false);
  if (phase === "complete") return "complete";
  if (phase === "posting" || phase === "decomposing") return "running";
  return "running";
}

function statusClass(label: string): string {
  if (label === "complete") return "bg-up/15 text-up";
  if (label === "posting") return "bg-gold/15 text-gold";
  return "bg-line/80 text-muted";
}

export function TaskHistorySidebar({ className }: { className?: string }) {
  const { taskEvents } = useFeed();
  const {
    pendingTasks,
    dbTasks,
    hiddenTaskIds,
    selectedTaskId,
    isNewChat,
    setSelectedTaskId,
    startNewChat,
    hideTask,
    tasksLoading,
  } = useNetwork();

  const threads = useMemo(() => {
    const live = buildPipelines(taskEvents, 0);
    return mergedTaskList(dbTasks, live, pendingTasks, hiddenTaskIds);
  }, [dbTasks, taskEvents, pendingTasks, hiddenTaskIds]);

  const activeId = useMemo(() => {
    if (isNewChat) return null;
    if (
      selectedTaskId &&
      threads.some((t) => {
        const id = t.kind === "pending" ? t.task.task_id : t.task.task_id;
        return id === selectedTaskId;
      })
    ) {
      return selectedTaskId;
    }
    return pickDefaultTaskId(threads);
  }, [selectedTaskId, threads, isNewChat]);

  return (
    <aside
      className={cn(
        "flex w-60 shrink-0 flex-col border-r border-line/60 bg-panel/30",
        className,
      )}
    >
      <div className="flex items-center justify-between gap-2 border-b border-line/60 px-3 py-2.5">
        <div className="font-mono text-[10px] uppercase tracking-wider text-dim">
          Chats
        </div>
        <button
          type="button"
          onClick={startNewChat}
          className="rounded-md border border-line/60 bg-base/50 px-2 py-1 font-mono text-[9px] uppercase tracking-wide text-muted transition-colors hover:border-gold/40 hover:text-gold"
          title="Start a new task"
        >
          New chat
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {tasksLoading && threads.length === 0 ? (
          <div className="px-3 py-4 font-mono text-[11px] text-dim">Loading…</div>
        ) : threads.length === 0 ? (
          <div className="px-3 py-4 text-[12px] leading-relaxed text-dim">
            No chats yet. Use New chat and post a goal to get started.
          </div>
        ) : (
          <ul className="py-1">
            {threads.map((view) => {
              const id =
                view.kind === "pending" ? view.task.task_id : view.task.task_id;
              const goal =
                view.kind === "pending" ? view.task.goal : view.task.goal;
              const ts =
                view.kind === "pending" ? view.task.postedAt : view.task.ts;
              const label = statusLabel(view);
              const selected = id === activeId;
              const complete =
                view.kind === "live" &&
                isTaskComplete(sortedSubtasks(view.task));

              return (
                <li key={id} className="group relative">
                  <button
                    type="button"
                    onClick={() => setSelectedTaskId(id)}
                    className={cn(
                      "w-full border-l-2 py-2.5 pl-3 pr-8 text-left transition-colors",
                      selected
                        ? "border-gold bg-gold/5"
                        : "border-transparent hover:bg-base/40",
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span
                        className={cn(
                          "line-clamp-2 text-[12px] leading-snug",
                          selected ? "text-ink" : "text-muted",
                        )}
                      >
                        {goal}
                      </span>
                    </div>
                    <div className="mt-1.5 flex items-center gap-2">
                      <span
                        className={cn(
                          "rounded px-1.5 py-0.5 font-mono text-[9px] uppercase",
                          statusClass(label),
                        )}
                      >
                        {complete ? "complete" : label}
                      </span>
                      <span className="font-mono text-[9px] text-faint">
                        {fmtTime(ts)}
                      </span>
                    </div>
                  </button>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      void hideTask(id);
                    }}
                    className="absolute right-2 top-2.5 rounded p-1 text-faint opacity-0 transition-opacity hover:bg-down/10 hover:text-down group-hover:opacity-100"
                    aria-label="Delete chat"
                    title="Remove from your history"
                  >
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <path
                        d="M3 3l6 6M9 3L3 9"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                      />
                    </svg>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </aside>
  );
}
