// Typed client for the FastAPI endpoints (api/main.py).

export interface Proposal {
  proposal_id: number;
  brand_id: string;
  campaign_id: string;
  sim_day: string;
  direction: "increase" | "decrease" | "hold";
  current_budget: number;
  requested_budget: number;
  final_budget: number;
  change_pct: number;
  reason: string;
  expected_effect: string;
  risk: "low" | "high";
  status: "pending" | "approved" | "rejected" | "auto_approved" | "blocked";
  guardrails: string[];
  reviewer: string | null;
  decision_reason: string | null;
}

export interface WindowMetrics {
  spend: number;
  revenue: number;
  conversions: number;
  clicks: number;
  roas: number | null;
  cpa: number | null;
}

export interface Campaign {
  campaign_id: string;
  brand_id: string;
  name: string;
  channel: string;
  objective: string;
  daily_budget: number;
  last_7_days: WindowMetrics | null;
}

export interface CampaignsResponse {
  data_through: string | null;
  brands: { brand_id: string; name: string; daily_budget_cap: number }[];
  campaigns: Campaign[];
}

export interface DailyPoint {
  day: string;
  spend: number;
  revenue: number;
  conversions: number;
  clicks: number;
  roas: number | null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "content-type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  experiments: () => request<string[]>("/experiments"),
  campaigns: (exp: string) => request<CampaignsResponse>(`/experiments/${exp}/campaigns`),
  proposals: (exp: string) => request<Proposal[]>(`/experiments/${exp}/proposals`),
  daily: (exp: string, cid: string) =>
    request<DailyPoint[]>(`/experiments/${exp}/campaigns/${cid}/daily?days=28`),
  decide: (exp: string, id: number, decision: "approve" | "reject", reason: string) =>
    request<Proposal>(`/experiments/${exp}/proposals/${id}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, reason }),
    }),
};
