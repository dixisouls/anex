import type { TaskState } from "./pipeline";

export interface PendingTask {
  task_id: string;
  goal: string;
  budget: number;
  postedAt: string;
}

export type TaskView =
  | { kind: "pending"; task: PendingTask }
  | { kind: "live"; task: TaskState };

export function mergeTaskThreads(
  pending: PendingTask[],
  pipelines: TaskState[],
): TaskView[] {
  const liveIds = new Set(pipelines.map((t) => t.task_id));
  const views: TaskView[] = [];

  for (const p of pending) {
    if (!liveIds.has(p.task_id)) {
      views.push({ kind: "pending", task: p });
    }
  }

  for (const t of pipelines) {
    views.push({ kind: "live", task: t });
  }

  views.sort((a, b) => {
    const ta = a.kind === "pending" ? a.task.postedAt : a.task.ts;
    const tb = b.kind === "pending" ? b.task.postedAt : b.task.ts;
    return ta < tb ? -1 : ta > tb ? 1 : 0;
  });

  return views;
}
