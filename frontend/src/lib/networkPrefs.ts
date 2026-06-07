const BROKER_MODEL_KEY = "anex.brokerModel";
export const DEFAULT_BROKER_MODEL = "gemini-3.5-flash";

export function loadBrokerModel(): string {
  if (typeof window === "undefined") return DEFAULT_BROKER_MODEL;
  return localStorage.getItem(BROKER_MODEL_KEY) ?? DEFAULT_BROKER_MODEL;
}

export function saveBrokerModel(modelId: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(BROKER_MODEL_KEY, modelId);
}
