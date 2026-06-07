import type { Tier } from "./types";

const BROKER_MODEL_KEY = "anex.brokerModel";
const PREFERRED_TIER_KEY = "anex.preferredTier";
export const DEFAULT_BROKER_MODEL = "gemini-3.5-flash";
export const DEFAULT_PREFERRED_TIER: Tier = "pro";

export function loadBrokerModel(): string {
  if (typeof window === "undefined") return DEFAULT_BROKER_MODEL;
  return localStorage.getItem(BROKER_MODEL_KEY) ?? DEFAULT_BROKER_MODEL;
}

export function saveBrokerModel(modelId: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(BROKER_MODEL_KEY, modelId);
}

export function loadPreferredTier(): Tier {
  if (typeof window === "undefined") return DEFAULT_PREFERRED_TIER;
  const v = localStorage.getItem(PREFERRED_TIER_KEY);
  if (v === "pro" || v === "flash" || v === "lite") return v;
  return DEFAULT_PREFERRED_TIER;
}

export function savePreferredTier(tier: Tier): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(PREFERRED_TIER_KEY, tier);
}

const SELECTED_TASK_KEY = "anex.networkSelectedTask";

export function loadSelectedTaskId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(SELECTED_TASK_KEY);
}

export function saveSelectedTaskId(taskId: string | null): void {
  if (typeof window === "undefined") return;
  if (taskId) localStorage.setItem(SELECTED_TASK_KEY, taskId);
  else localStorage.removeItem(SELECTED_TASK_KEY);
}

function hiddenTasksKey(userId: string): string {
  return `anex.hiddenTasks.${userId}`;
}

export function loadHiddenTaskIds(userId: string): Set<string> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = localStorage.getItem(hiddenTasksKey(userId));
    if (!raw) return new Set();
    const parsed = JSON.parse(raw) as string[];
    return new Set(Array.isArray(parsed) ? parsed : []);
  } catch {
    return new Set();
  }
}

export function saveHiddenTaskIds(userId: string, ids: Set<string>): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(hiddenTasksKey(userId), JSON.stringify([...ids]));
}
