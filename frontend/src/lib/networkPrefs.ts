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
