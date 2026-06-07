"use client";

import { useEffect, useMemo, useRef } from "react";
import { useFeed } from "@/lib/feed";
import { useNetwork } from "@/lib/networkContext";
import { buildPipelines } from "@/lib/pipeline";
import { mergeTaskThreads } from "@/lib/taskThread";
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
  const { events } = useFeed();
  const { pendingTasks, scrollNonce, removePendingTask, bumpScroll } =
    useNetwork();
  const bottomRef = useRef<HTMLDivElement>(null);

  const pipelines = useMemo(() => buildPipelines(events), [events]);
  const threads = useMemo(
    () => mergeTaskThreads(pendingTasks, pipelines),
    [pendingTasks, pipelines],
  );

  useEffect(() => {
    for (const p of pipelines) {
      removePendingTask(p.task_id);
    }
  }, [pipelines, removePendingTask]);

  useEffect(() => {
    bumpScroll();
  }, [events.length, pendingTasks.length, bumpScroll]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [scrollNonce, threads.length, events.length]);

  if (threads.length === 0) {
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
            results step by step.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("min-h-0 flex-1 overflow-y-auto", className)}>
      <div className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-6">
        {threads.map((view) => (
          <TaskBlock
            key={
              view.kind === "pending" ? view.task.task_id : view.task.task_id
            }
            view={view}
            agents={agents}
          />
        ))}
        <div ref={bottomRef} className="h-px shrink-0" />
      </div>
    </div>
  );
}
