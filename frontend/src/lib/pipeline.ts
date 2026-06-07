// Derives live task-pipeline state from the rolling SSE event log.
import type { Candidate, FeedEvent } from "./types";

export type Stage = "posted" | "ranked" | "hired" | "executed" | "scored";

export const STAGE_ORDER: Stage[] = [
  "posted",
  "ranked",
  "hired",
  "executed",
  "scored",
];

export interface SubtaskState {
  subtask_id: string;
  index: number;
  text: string;
  candidates: Candidate[];
  hiredAgentId?: string;
  output?: string;
  score?: number;
  stage: Stage;
  hirePrice?: number;
  budgetRemaining?: number;
  skipped?: boolean;
  skipReason?: string;
}

export interface TaskState {
  task_id: string;
  goal: string;
  ts: string;
  subtasks: Record<string, SubtaskState>;
}

function taskIdOf(subtaskId: string): string {
  return subtaskId.slice(0, subtaskId.lastIndexOf("-"));
}

function indexOf(subtaskId: string): number {
  const n = parseInt(subtaskId.slice(subtaskId.lastIndexOf("-") + 1), 10);
  return Number.isNaN(n) ? 0 : n;
}

function bump(s: SubtaskState, stage: Stage) {
  if (STAGE_ORDER.indexOf(stage) > STAGE_ORDER.indexOf(s.stage)) s.stage = stage;
}

/** events are newest-first; we fold them oldest-first into task state. */
export function buildPipelines(events: FeedEvent[], limit = 8): TaskState[] {
  const tasks: Record<string, TaskState> = {};

  const ensureSub = (taskId: string, subtaskId: string): SubtaskState | null => {
    const t = tasks[taskId];
    if (!t) return null;
    if (!t.subtasks[subtaskId]) {
      t.subtasks[subtaskId] = {
        subtask_id: subtaskId,
        index: indexOf(subtaskId),
        text: "",
        candidates: [],
        stage: "posted",
      };
    }
    return t.subtasks[subtaskId];
  };

  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i];
    switch (e.type) {
      case "task_posted": {
        tasks[e.task_id] = {
          task_id: e.task_id,
          goal: e.goal,
          ts: e.ts,
          subtasks: {},
        };
        for (const st of e.subtasks) {
          tasks[e.task_id].subtasks[st.subtask_id] = {
            subtask_id: st.subtask_id,
            index: indexOf(st.subtask_id),
            text: st.text,
            candidates: [],
            stage: "posted",
          };
        }
        break;
      }
      case "candidates_ranked": {
        const s = ensureSub(taskIdOf(e.subtask_id), e.subtask_id);
        if (s) {
          s.candidates = e.candidates;
          bump(s, "ranked");
        }
        break;
      }
      case "agent_hired": {
        const s = ensureSub(taskIdOf(e.subtask_id), e.subtask_id);
        if (s) {
          s.hiredAgentId = e.agent_id;
          s.hirePrice = e.price;
          s.budgetRemaining = e.budget_remaining;
          s.skipped = false;
          bump(s, "hired");
        }
        break;
      }
      case "subtask_skipped": {
        const s = ensureSub(taskIdOf(e.subtask_id), e.subtask_id);
        if (s) {
          s.skipped = true;
          s.skipReason = e.reason;
        }
        break;
      }
      case "task_executed": {
        const s = ensureSub(taskIdOf(e.subtask_id), e.subtask_id);
        if (s) {
          s.output = e.output_preview;
          if (!s.hiredAgentId) s.hiredAgentId = e.agent_id;
          bump(s, "executed");
        }
        break;
      }
      case "task_scored": {
        const s = ensureSub(taskIdOf(e.subtask_id), e.subtask_id);
        if (s) {
          s.score = e.judge_score;
          bump(s, "scored");
        }
        break;
      }
    }
  }

  return Object.values(tasks)
    .sort((a, b) => (a.ts < b.ts ? 1 : -1))
    .slice(0, limit);
}
