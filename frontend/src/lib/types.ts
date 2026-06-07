// Type mirrors of the ANEX backend (contracts/schemas.py, contracts/events.py)
// and the FastAPI response shapes in backend/api/app.py.

export type Provider = "gcp" | "openai" | "vertex_openai";
export type Tier = "pro" | "flash" | "lite";
export type Side = "buy" | "sell";

export interface Agent {
  agent_id: string;
  name: string;
  skills: string[];
  capability_text: string;
  model: string;
  tools: string[];
  reputation: number;
  credits: number;
  margin: number;
  price: number | null;
  hires: number;
  wins: number;
}

export interface ModelStock {
  model_id: string;
  name: string;
  provider: Provider;
  tier: Tier;
  price: number;
  shares: number;
  credits: number;
  executable: boolean;
}

export interface PriceTick {
  id?: string;
  model_id: string;
  price: number;
}

export interface MarketResponse {
  models: ModelStock[];
  history: PriceTick[];
}

export interface Holding {
  model_id: string;
  shares: number;
  price: number;
  value: number;
}

export interface Portfolio {
  user_id: string;
  credits: number;
  holdings: Holding[];
  holdings_value: number;
  total: number;
}

export interface UserPublic {
  user_id: string;
  name: string;
  email: string | null;
  credits: number;
  is_sim: boolean;
  net_worth: number | null;
}

export interface AuthUser {
  user_id: string;
  name: string;
  email: string;
  credits: number;
}

export interface EarningsRow {
  event_id?: string;
  ts: string;
  agent_id: string;
  amount: number;
  judge_score: number | null;
}

export interface TaskSlots {
  max: number;
  available: number;
  in_use: number;
}

export interface TradeResult {
  trade_id: string;
  price: number;
  shares: number;
  credits: number;
}

export interface Subtask {
  subtask_id: string;
  text: string;
}

export interface Candidate {
  agent_id: string;
  match_score: number;
  reputation: number;
  price: number;
  final_score: number;
}

// ── SSE events ──────────────────────────────────────────────────────────────

interface EventBase {
  event_id: string;
  ts: string;
  type: string;
}

export interface TaskPostedEvent extends EventBase {
  type: "task_posted";
  task_id: string;
  goal: string;
  subtasks: Subtask[];
}

export interface CandidatesRankedEvent extends EventBase {
  type: "candidates_ranked";
  subtask_id: string;
  candidates: Candidate[];
}

export interface AgentHiredEvent extends EventBase {
  type: "agent_hired";
  subtask_id: string;
  agent_id: string;
  price: number;
  budget_remaining: number;
}

export interface SubtaskSkippedEvent extends EventBase {
  type: "subtask_skipped";
  subtask_id: string;
  reason: string;
}

export interface TaskExecutedEvent extends EventBase {
  type: "task_executed";
  subtask_id: string;
  agent_id: string;
  output_preview: string;
}

export interface TaskScoredEvent extends EventBase {
  type: "task_scored";
  subtask_id: string;
  agent_id: string;
  judge_score: number;
}

export interface ReputationChangedEvent extends EventBase {
  type: "reputation_changed";
  agent_id: string;
  old: number;
  new: number;
}

export interface CreditsChangedEvent extends EventBase {
  type: "credits_changed";
  agent_id: string;
  old: number;
  new: number;
}

export interface ModelListedEvent extends EventBase {
  type: "model_listed";
  model_id: string;
  name: string;
  provider: Provider;
  tier: Tier;
  ipo_price: number;
}

export interface PriceChangedEvent extends EventBase {
  type: "price_changed";
  model_id: string;
  old: number;
  new: number;
  reason: string;
}

export interface EarningsInjectedEvent extends EventBase {
  type: "earnings_injected";
  model_id: string;
  agent_id: string;
  amount: number;
  judge_score: number;
}

export interface TradeExecutedEvent extends EventBase {
  type: "trade_executed";
  trade_id: string;
  user_id: string;
  model_id: string;
  side: Side;
  shares: number;
  credits: number;
  price: number;
}

export interface PortfolioChangedEvent extends EventBase {
  type: "portfolio_changed";
  user_id: string;
  credits: number;
  holdings_value: number;
  total: number;
}

export type FeedEvent =
  | TaskPostedEvent
  | CandidatesRankedEvent
  | AgentHiredEvent
  | SubtaskSkippedEvent
  | TaskExecutedEvent
  | TaskScoredEvent
  | ReputationChangedEvent
  | CreditsChangedEvent
  | ModelListedEvent
  | PriceChangedEvent
  | EarningsInjectedEvent
  | TradeExecutedEvent
  | PortfolioChangedEvent;

export type FeedEventType = FeedEvent["type"];
