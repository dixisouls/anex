// Deterministic ticker symbols + issuer labels for model-stocks.
import type { Provider, Tier } from "./types";

const SYMBOLS: Record<string, string> = {
  "gemini-3.1-pro-preview": "GEM3P",
  "gemini-3.5-flash": "GEM35",
  "gemini-3.1-flash-lite": "GEMFL",
  "gemma-4-26b-a4b-it-maas": "GMA4",
  "meta/llama-4-maverick-17b-128e-instruct-maas": "LMA4",
  "xai/grok-4.1-fast-non-reasoning": "GRK41",
  "xai/grok-4.20-non-reasoning": "GRK42",
  "xai/grok-4.1-fast-reasoning": "GRK41R",
  "xai/grok-4.20-reasoning": "GRK42R",
  "zai-org/glm-5-maas": "GLM5",
  "gpt-5.5": "GPT55",
  "gpt-5.4-mini": "GPT54M",
  "gpt-4.1": "GPT41",
  "gpt-4.1-mini": "GPT41M",
};

export function tickerSymbol(modelId: string): string {
  if (SYMBOLS[modelId]) return SYMBOLS[modelId];
  const bare = modelId.split("/").pop() ?? modelId;
  const letters = bare.replace(/[^a-zA-Z]/g, "").slice(0, 3).toUpperCase();
  const nums = bare.replace(/[^0-9]/g, "").slice(0, 2);
  return (letters + nums).slice(0, 6) || bare.slice(0, 6).toUpperCase();
}

export function issuer(provider: Provider, modelId: string): string {
  if (provider === "openai") return "OpenAI";
  if (provider === "gcp") return "Google";
  if (modelId.startsWith("xai/")) return "xAI";
  if (modelId.startsWith("meta/")) return "Meta";
  if (modelId.startsWith("zai-org/")) return "Z.ai";
  return "Vertex";
}

export const TIER_LABEL: Record<Tier, string> = {
  pro: "PRO",
  flash: "FLASH",
  lite: "LITE",
};

// tier → tailwind text/border classes
export const TIER_CLASS: Record<Tier, string> = {
  pro: "text-gold border-gold-dim",
  flash: "text-info border-info/40",
  lite: "text-muted border-line-bright",
};
