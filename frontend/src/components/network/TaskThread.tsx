"use client";

import { useEffect, useMemo, useRef } from "react";
import { useFeed } from "@/lib/feed";
import { useNetwork } from "@/lib/networkContext";
import { buildPipelines } from "@/lib/pipeline";
import {
  mergedTaskList,
  pickDefaultTaskId,
} from "@/lib/taskThread";
import { TaskBlock } from "./TaskBlock";
import { cn } from "@/lib/cn";
import type { Agent } from "@/lib/types";

export function TaskThread({
  agents,
  className,
}: {
  agents: Record<string, Agent>;
  className?: string;
}) {
  const { taskEvents } = useFeed();
  const {
    pendingTasks,
    dbTasks,
    hiddenTaskIds,
    selectedTaskId,
    isNewChat,
    setSelectedTaskId,
    hideTask,
    scrollNonce,
    removePendingTask,
    bumpScroll,
  } = useNetwork();
  const bottomRef = useRef<HTMLDivElement>(null);

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

  const selectedView = useMemo(
    () =>
      activeId
        ? (threads.find((t) => {
            const id = t.kind === "pending" ? t.task.task_id : t.task.task_id;
            return id === activeId;
          }) ?? null)
        : null,
    [threads, activeId],
  );

  useEffect(() => {
    if (isNewChat) return;
    if (activeId && activeId !== selectedTaskId) {
      setSelectedTaskId(activeId);
    }
  }, [activeId, selectedTaskId, setSelectedTaskId, isNewChat]);

  useEffect(() => {
    for (const p of buildPipelines(taskEvents, 0)) {
      removePendingTask(p.task_id);
    }
  }, [taskEvents, removePendingTask]);

  useEffect(() => {
    bumpScroll();
  }, [taskEvents.length, pendingTasks.length, bumpScroll]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [scrollNonce, selectedView, taskEvents.length]);

  if (!selectedView) {
    return (
      <div
        className={cn(
          "grid flex-1 place-items-center p-8 text-center",
          className,
        )}
      >
        <div className="max-w-md">
          <div className="text-base text-muted">How can the network help?</div>
          <div className="mt-2 text-[13px] leading-relaxed text-dim">
            Post a goal and watch agents decompose, bid, execute, and deliver
            results step by step. Your tasks are saved in the sidebar.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("min-h-0 flex-1 overflow-y-auto", className)}>
      <div className="mx-auto flex max-w-3xl flex-col gap-4 px-4 py-6">
        <div className="flex justify-end">
          <button
            type="button"
            onClick={() => void hideTask(selectedView.kind === "pending"
              ? selectedView.task.task_id
              : selectedView.task.task_id)}
            className="font-mono text-[10px] text-dim transition-colors hover:text-down"
          >
            Delete chat
          </button>
        </div>
        <TaskBlock view={selectedView} agents={agents} />
        <div ref={bottomRef} className="h-px shrink-0" />
      </div>
    </div>
  );
}
