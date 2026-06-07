import type { TaskDetail } from "./types";
import {
  isTaskComplete,
  sortedSubtasks,
  STAGE_ORDER,
  type Stage,
  type SubtaskState,
  type TaskState,
} from "./pipeline";

export interface PendingTask {
  task_id: string;
  goal: string;
  budget: number;
  postedAt: string;
}

export type TaskView =
  | { kind: "pending"; task: PendingTask }
  | { kind: "live"; task: TaskState };

function indexOf(subtaskId: string): number {
  const n = parseInt(subtaskId.slice(subtaskId.lastIndexOf("-") + 1), 10);
  return Number.isNaN(n) ? 0 : n;
}

function stageIndex(stage: Stage): number {
  const i = STAGE_ORDER.indexOf(stage);
  return i < 0 ? 0 : i;
}

function maxStage(a: Stage, b: Stage): Stage {
  return stageIndex(b) > stageIndex(a) ? b : a;
}

function stageFromDetail(st: TaskDetail["subtasks"][number]): Stage {
  if (st.judge_score != null) return "scored";
  if (st.output_preview) return "executed";
  if (st.assigned_agent_id) return "hired";
  const s = st.stage as Stage;
  if (s === "scored" || s === "executed" || s === "hired" || s === "ranked") return s;
  return "posted";
}

export function taskDetailToState(t: TaskDetail): TaskState {
  const subtasks: Record<string, SubtaskState> = {};
  for (const st of t.subtasks) {
    const stage = stageFromDetail(st);
    subtasks[st.subtask_id] = {
      subtask_id: st.subtask_id,
      index: indexOf(st.subtask_id),
      text: st.text,
      candidates: st.candidates ?? [],
      stage,
      hiredAgentId: st.assigned_agent_id ?? undefined,
      output: st.output_preview ?? undefined,
      score: st.judge_score ?? undefined,
      hirePrice: st.hire_price ?? undefined,
      budgetRemaining: st.budget_remaining ?? undefined,
      skipped: st.skipped ?? undefined,
      skipReason: st.skip_reason ?? undefined,
      skipMessage: st.skip_message ?? undefined,
    };
  }
  return {
    task_id: t.task_id,
    goal: t.goal,
    ts: t.created_at,
    subtasks,
  };
}

function overlaySubtask(base: SubtaskState, live: SubtaskState): SubtaskState {
  const stage = maxStage(base.stage, live.stage);
  return {
    ...base,
    text: live.text || base.text,
    candidates: live.candidates.length ? live.candidates : base.candidates,
    hiredAgentId: live.hiredAgentId ?? base.hiredAgentId,
    output: base.output ?? live.output,
    score: base.score ?? live.score,
    stage,
    hirePrice: live.hirePrice ?? base.hirePrice,
    budgetRemaining: live.budgetRemaining ?? base.budgetRemaining,
    skipped: live.skipped ?? base.skipped,
    skipReason: live.skipReason ?? base.skipReason,
    skipMessage: live.skipMessage ?? base.skipMessage,
  };
}

export function overlayTaskState(base: TaskState, live: TaskState): TaskState {
  const subtasks = { ...base.subtasks };
  for (const [id, liveSub] of Object.entries(live.subtasks)) {
    subtasks[id] = subtasks[id]
      ? overlaySubtask(subtasks[id], liveSub)
      : liveSub;
  }
  return {
    task_id: base.task_id,
    goal: live.goal || base.goal,
    ts: live.ts || base.ts,
    subtasks,
  };
}

export function mergeTaskStates(
  dbTasks: Record<string, TaskState>,
  livePipelines: TaskState[],
): Record<string, TaskState> {
  const merged = { ...dbTasks };
  for (const live of livePipelines) {
    const existing = merged[live.task_id];
    if (!existing) {
      merged[live.task_id] = live;
      continue;
    }
    // Completed tasks: DB is source of truth (full persisted pipeline).
    if (isTaskComplete(sortedSubtasks(existing))) {
      continue;
    }
    merged[live.task_id] = overlayTaskState(existing, live);
  }
  return merged;
}

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

export function filterHiddenThreads(
  threads: TaskView[],
  hiddenIds: Set<string>,
): TaskView[] {
  if (hiddenIds.size === 0) return threads;
  return threads.filter((t) => {
    const id = t.kind === "pending" ? t.task.task_id : t.task.task_id;
    return !hiddenIds.has(id);
  });
}

export function mergedTaskList(
  dbTasks: Record<string, TaskState>,
  livePipelines: TaskState[],
  pending: PendingTask[],
  hiddenIds: Set<string> = new Set(),
): TaskView[] {
  const merged = mergeTaskStates(dbTasks, livePipelines);
  return filterHiddenThreads(
    mergeTaskThreads(pending, Object.values(merged)),
    hiddenIds,
  );
}

export function pickDefaultTaskId(threads: TaskView[]): string | null {
  if (threads.length === 0) return null;
  const running = [...threads].reverse().find((t) => {
    if (t.kind === "pending") return true;
    const subs = Object.values(t.task.subtasks);
    if (subs.length === 0) return true;
    return subs.some((s) => !s.skipped && s.stage !== "scored");
  });
  if (running) {
    return running.kind === "pending" ? running.task.task_id : running.task.task_id;
  }
  const last = threads[threads.length - 1];
  return last.kind === "pending" ? last.task.task_id : last.task.task_id;
}
