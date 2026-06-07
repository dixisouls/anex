// Typed REST client for the ANEX backend (FastAPI on :8000).
import type {
  Agent,
  AuthUser,
  EarningsRow,
  MarketResponse,
  ModelStock,
  Portfolio,
  Side,
  TaskSlots,
  TradeResult,
  UserPublic,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  getAgents: () => req<Agent[]>("/agents"),
  getModels: () => req<ModelStock[]>("/models"),
  getMarket: () => req<MarketResponse>("/market"),
  getTaskSlots: () => req<TaskSlots>("/task/slots"),
  getEarnings: (modelId: string, limit = 20) =>
    req<EarningsRow[]>(
      `/models/${encodeURIComponent(modelId)}/earnings?limit=${limit}`,
    ),

  postTask: (goal: string, user_id?: string, budget?: number) =>
    req<{ task_id: string; budget: number }>("/task", {
      method: "POST",
      body: JSON.stringify({ goal, user_id, budget }),
    }),

  register: (email: string, password: string, name?: string) =>
    req<AuthUser>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, name }),
    }),

  login: (email: string, password: string) =>
    req<AuthUser>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  trade: (user_id: string, model_id: string, side: Side, amount: number) =>
    req<TradeResult>("/trade", {
      method: "POST",
      body: JSON.stringify({ user_id, model_id, side, amount }),
    }),

  getPortfolio: (user_id: string) =>
    req<Portfolio>(`/portfolio/${user_id}`),

  createUser: (name: string, email?: string, is_sim = false) =>
    req<{ user_id: string }>("/users", {
      method: "POST",
      body: JSON.stringify({ name, email, is_sim }),
    }),

  getUsers: () => req<UserPublic[]>("/users"),

  // Demo / simulation controls
  seed: () => req<{ ok: boolean; agents: number; models: number; users: number }>(
    "/seed",
    { method: "POST" },
  ),
  simStart: (body?: {
    n_posters?: number;
    n_investors?: number;
    cadence_s?: number;
  }) =>
    req<{ ok: boolean; note: string }>("/sim/start", {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
  simStop: () => req<{ ok: boolean }>("/sim/stop", { method: "POST" }),
};

export { ApiError };
