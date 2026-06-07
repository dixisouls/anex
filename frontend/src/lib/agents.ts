// Agent categorisation + display helpers.

export const CATEGORIES = [
  "Content",
  "Engineering",
  "Research",
  "Language",
  "Strategy",
  "Reasoning",
] as const;

export type Category = (typeof CATEGORIES)[number];

const PREFIX_CATEGORY: Record<string, Category> = {
  writer: "Content",
  blogger: "Content",
  "technical-writer": "Content",
  "seo-writer": "Content",
  storyteller: "Content",
  marketer: "Content",
  "social-media": "Content",

  coder: "Engineering",
  debugger: "Engineering",
  reviewer: "Engineering",
  devops: "Engineering",
  "sql-analyst": "Engineering",
  security: "Engineering",

  researcher: "Research",
  analyst: "Research",
  factcheck: "Research",
  "market-analyst": "Research",
  "legal-analyst": "Research",

  translator: "Language",
  proofreader: "Language",
  summarizer: "Language",
  extractor: "Language",

  planner: "Strategy",
  strategist: "Strategy",
  "product-manager": "Strategy",

  "math-solver": "Reasoning",
  scientist: "Reasoning",
  economist: "Reasoning",
  classifier: "Reasoning",
  prompter: "Reasoning",

  "newsletter-writer": "Content",
  "whitepaper-writer": "Content",
  "video-scriptwriter": "Content",
  "ml-engineer": "Engineering",
  "frontend-dev": "Engineering",
  "competitive-intel": "Research",
  "policy-researcher": "Research",
  localization: "Language",
  "meeting-notes": "Language",
  "gtm-planner": "Strategy",
  "forecast-analyst": "Reasoning",
};

export function agentCategory(agentId: string): Category {
  const base = agentId.replace(/-(pro|flash|lite)$/, "");
  return PREFIX_CATEGORY[base] ?? "Reasoning";
}

export const SUGGESTED_GOALS = [
  "Write a launch announcement for an AI-powered note-taking app, then proofread it.",
  "Analyze the pros and cons of constant-product AMMs for a non-technical audience.",
  "Generate a Python function to compute a moving average, with edge-case handling.",
  "Research the current state of small open-weight language models and summarize key trends.",
  "Draft a go-to-market strategy for a developer tools startup, then refine the messaging.",
];
