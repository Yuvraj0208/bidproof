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
  document_id: string;
  page_no: number;
  bbox: { x0: number; y0: number; x1: number; y1: number };
  source: string;
  status: string;
  confidence: number;
  band: "green" | "yellow" | "red";
  reason: string;
}

export interface Amendment {
  id: string;
  document_id: string;
  message: string;
  changes: {
    key: string;
    family: string;
    change: string;
    old_value: string | null;
    new_value: string | null;
    page: number | null;
  }[];
  rules_affected: string[];
  rules_broken: string[];
  ev_before_inr: number | null;
  ev_after_inr: number | null;
  created_at: string;
}

export const fetchAmendments = (tenderId: string) =>
  request<Amendment[]>(`/tenders/${tenderId}/amendments`);

export interface QueryLetter {
  id: string;
  rule_id: string;
  rule_key: string;
  el_id: string;
  page_no: number;
  subject: string;
  body: string;
  query_deadline: string | null;
  status: string;
}

export const fetchQuestions = (tenderId: string) =>
  request<QueryLetter[]>(`/tenders/${tenderId}/questions`);

export const generateQuestions = (tenderId: string) =>
  request<{ letters: number }>(`/tenders/${tenderId}/questions`, {
    method: "POST",
  });

export interface ProposalClaim {
  text: string;
  source_tag: string | null;
  status: "verified" | "cannot_verify" | "contradicted";
}

export interface ProposalSection {
  id: string;
  section_tag: string;
  position: number;
  content: string;
  claims: ProposalClaim[];
  verified_pct: number | null;
  requirements_covered_pct: number | null;
  style_match_pct: number | null;
  dropped_untagged: number;
  approved: boolean;
  approved_by: string | null;
  open_flags: string[];
}

export interface Proposal {
  id: string;
  tender_id: string;
  status: string;
  format_source: string;
  duration_ms: number | null;
  sections: ProposalSection[];
}

export const fetchProposal = (tenderId: string) =>
  request<Proposal>(`/tenders/${tenderId}/proposal`);

export const generateProposal = (tenderId: string) =>
  request<{ sections: number; duration_ms: number }>(
    `/tenders/${tenderId}/proposal`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" },
  );

export const approveSection = (tenderId: string, sectionId: string, name: string) =>
  request<ProposalSection>(
    `/tenders/${tenderId}/proposal/sections/${sectionId}/approve`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    },
  );

export const editSection = (tenderId: string, sectionId: string, content: string) =>
  request<ProposalSection>(
    `/tenders/${tenderId}/proposal/sections/${sectionId}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    },
  );

export const fetchReadiness = (tenderId: string) =>
  request<{ total: number; approved: number; ready: boolean }>(
    `/tenders/${tenderId}/proposal/readiness`,
  );

export async function amendTender(tenderId: string, file: File): Promise<Amendment> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${API_BASE}/tenders/${tenderId}/amend`, {
    method: "POST",
    headers: { "X-Org-Id": getOrgId() },
    body: form,
  });
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  return response.json();
}

export const fetchRadar = (list?: string) =>
  request<RadarCard[]>(`/radar${list ? `?list=${list}` : ""}`);

export const fetchRules = (tenderId: string) =>
  request<Rule[]>(`/tenders/${tenderId}/rules`);

export interface Verdict {
  id: string;
  rule_id: string;
  family: string;
  key: string;
  requirement_text: string;
  value: string | null;
  verdict: string;
  reason: string;
  confidence: number;
  band: "green" | "yellow" | "red";
  arithmetic: boolean;
  document_id: string;
  page_no: number;
  bbox: { x0: number; y0: number; x1: number; y1: number };
}

export const fetchVerdicts = (tenderId: string) =>
  request<Verdict[]>(`/tenders/${tenderId}/verdicts`);

export const runCheck = (tenderId: string) =>
  request<{ rules_checked: number }>(`/tenders/${tenderId}/check`, {
    method: "POST",
  });

export const computeDecision = (tenderId: string, tenderValueInr?: number) =>
  request<unknown>(`/tenders/${tenderId}/decide`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(
      tenderValueInr != null ? { tender_value_inr: tenderValueInr } : {},
    ),
  });

export const fetchBrief = (tenderId: string) =>
  request<{
    decision: unknown;
    top_risks: unknown[];
  }>(`/tenders/${tenderId}/brief`);

export const signOffDecision = (tenderId: string, name: string) =>
  request<unknown>(`/tenders/${tenderId}/decision/signoff`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });

export const overrideDecision = (
  tenderId: string,
  name: string,
  recommendation: string,
  reason: string,
) =>
  request<unknown>(`/tenders/${tenderId}/decision/override`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, recommendation, reason }),
  });

export const fetchAgentRuns = (tenderId: string) =>
  request<{ runs: unknown[]; totals: unknown }>(
    `/tenders/${tenderId}/agent-runs`,
  );

export const replayTender = (tenderId: string) =>
  request<{ replayed: boolean }>(`/tenders/${tenderId}/replay`, {
    method: "POST",
  });

export async function downloadMatrix(tenderId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/tenders/${tenderId}/matrix.xlsx`, {
    headers: { "X-Org-Id": getOrgId() },
  });
  if (!response.ok) throw new Error(`${response.status}`);
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `matrix-${tenderId}.xlsx`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export const runExtraction = (tenderId: string) =>
  request<{ rules: number }>(`/tenders/${tenderId}/extract`, { method: "POST" });

export async function fetchDocumentBlob(tenderId: string): Promise<ArrayBuffer> {
  const response = await fetch(`${API_BASE}/tenders/${tenderId}/document`, {
    headers: { "X-Org-Id": getOrgId() },
  });
  if (!response.ok) throw new Error(`${response.status}`);
  return response.arrayBuffer();
}

export async function fetchDocumentBlobById(
  documentId: string,
): Promise<ArrayBuffer> {
  const response = await fetch(`${API_BASE}/documents/${documentId}/file`, {
    headers: { "X-Org-Id": getOrgId() },
  });
  if (!response.ok) throw new Error(`${response.status}`);
  return response.arrayBuffer();
}
