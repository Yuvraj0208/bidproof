// API client. The org context header is the temporary tenancy mechanism
// until US-16 brings real auth — same contract the backend enforces.
export const API_BASE = "http://localhost:8000";

export function getOrgId(): string {
  return localStorage.getItem("bidproof_org_id") ?? "";
}

export function setOrgId(orgId: string): void {
  localStorage.setItem("bidproof_org_id", orgId);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "X-Org-Id": getOrgId(), ...(init?.headers ?? {}) },
  });
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  return response.json() as Promise<T>;
}

export interface RadarCard {
  tender_id: string;
  title: string;
  source: string;
  external_id: string | null;
  closing_at: string | null;
  radar_list: string;
  fit_score: number | null;
  confidence: number | null;
  band: "green" | "yellow" | "red" | null;
  matched_category: string | null;
  reasons: string[];
  checkpoint0: string | null;
}

export interface Rule {
  rule_id: string;
  family: string;
  key: string;
  requirement_text: string;
  value: string | null;
  el_id: string;
  page_no: number;
  bbox: { x0: number; y0: number; x1: number; y1: number };
  source: string;
  status: string;
  confidence: number;
  band: "green" | "yellow" | "red";
  reason: string;
}

export const fetchRadar = (list?: string) =>
  request<RadarCard[]>(`/radar${list ? `?list=${list}` : ""}`);

export const fetchRules = (tenderId: string) =>
  request<Rule[]>(`/tenders/${tenderId}/rules`);

export const runExtraction = (tenderId: string) =>
  request<{ rules: number }>(`/tenders/${tenderId}/extract`, { method: "POST" });

export async function fetchDocumentBlob(tenderId: string): Promise<ArrayBuffer> {
  const response = await fetch(`${API_BASE}/tenders/${tenderId}/document`, {
    headers: { "X-Org-Id": getOrgId() },
  });
  if (!response.ok) throw new Error(`${response.status}`);
  return response.arrayBuffer();
}
