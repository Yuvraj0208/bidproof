// API client. The org context header is the temporary tenancy mechanism
// until US-16 brings real auth — same contract the backend enforces.
export const API_BASE = "http://localhost:8000";

export function getOrgId(): string {
  return localStorage.getItem("bidproof_org_id") ?? "";
}

export function setOrgId(orgId: string): void {
  localStorage.setItem("bidproof_org_id", orgId);
}

export const ROLES = [
  "viewer",
  "bid_executive",
  "reviewer",
  "bid_head",
  "admin",
  "auditor",
] as const;
export type RoleName = (typeof ROLES)[number];

export function getRole(): RoleName {
  return (localStorage.getItem("bidproof_role") as RoleName) ?? "bid_executive";
}

export function setRole(role: RoleName): void {
  localStorage.setItem("bidproof_role", role);
}

export function authHeaders(): Record<string, string> {
  return { "X-Org-Id": getOrgId(), "X-Role": getRole() };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...authHeaders(), ...(init?.headers ?? {}) },
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

export interface LearnedPrefill {
  suggested_value: string;
  note: string;
  based_on_count: number;
  source_tender_id: string | null;
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
  // US-20: a pre-fill carried from past corrections — always shown, never silent.
  learned: LearnedPrefill | null;
}

export const correctRule = (
  tenderId: string,
  ruleId: string,
  correctedValue: string,
  name: string,
) =>
  request<{ correction_id: string; key: string; is_label: boolean; message: string }>(
    `/tenders/${tenderId}/rules/${ruleId}/correct`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ corrected_value: correctedValue, name }),
    },
  );

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

export interface ChatCitation {
  el_id: string;
  page_no: number;
}

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
  citations: ChatCitation[];
  refused: boolean;
  reason: string | null;
}

export const fetchChatHistory = (tenderId: string) =>
  request<ChatTurn[]>(`/tenders/${tenderId}/chat`);

export const askChat = (tenderId: string, question: string) =>
  request<{
    answer: string;
    citations: ChatCitation[];
    refused: boolean;
    reason: string | null;
  }>(`/tenders/${tenderId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });

export interface ChecklistItem {
  id: string;
  name: string;
  required: boolean;
  required_format: string;
  signature_required: boolean;
  uploaded_format: string | null;
  signature_present: boolean | null;
  checks_pass: boolean;
  checks_reason: string | null;
  ticked: boolean;
  ticked_by: string | null;
}

export interface Checklist {
  items: ChecklistItem[];
  required_count: number;
  ticked_count: number;
  submit_ready: boolean;
}

export const fetchChecklist = (tenderId: string) =>
  request<Checklist>(`/tenders/${tenderId}/checklist`);

export const generateChecklist = (tenderId: string) =>
  request<Checklist>(`/tenders/${tenderId}/checklist`, { method: "POST" });

export const attachChecklistFile = (
  itemId: string,
  format: string,
  signed: boolean,
) =>
  request<ChecklistItem>(`/checklist/items/${itemId}/attach`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ format, signed }),
  });

export const tickChecklistItem = (itemId: string, name: string) =>
  request<ChecklistItem>(`/checklist/items/${itemId}/tick`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });

export interface ExportBlocker {
  type: string;
  message: string;
  rule_key?: string;
  section?: string;
}

export const exportPreflight = (tenderId: string) =>
  request<{ can_export: boolean; blockers: ExportBlocker[] }>(
    `/tenders/${tenderId}/proposal/export/preflight`,
  );

// Returns null and the blockers when export is refused; downloads the .docx
// (and returns []) when it succeeds.
export async function exportProposal(
  tenderId: string,
  override?: { name: string; reason: string },
): Promise<ExportBlocker[]> {
  const response = await fetch(`${API_BASE}/tenders/${tenderId}/proposal/export`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(
      override
        ? { override_name: override.name, override_reason: override.reason }
        : {},
    ),
  });
  if (response.status === 409) {
    const body = await response.json();
    return (body.detail?.blockers ?? []) as ExportBlocker[];
  }
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `proposal-${tenderId}.docx`;
  anchor.click();
  URL.revokeObjectURL(url);
  return [];
}

export async function amendTender(tenderId: string, file: File): Promise<Amendment> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${API_BASE}/tenders/${tenderId}/amend`, {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  return response.json();
}

export interface LeaderboardRow {
  model: string;
  kind: string;
  f1_overall: number;
  f1_eligibility: number;
  exact_numbers: number | null;
  hallucination_rate: number;
  citation_complete: number;
  speed_ms: number;
  cost_per_tender_inr: number;
  simulated: boolean;
}

export interface ModelLabResult {
  role: string;
  gold_tenders: number;
  simulated: boolean;
  leaderboard: LeaderboardRow[];
}

export const runModelLab = (role = "extraction") =>
  request<ModelLabResult>(`/modellab/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role }),
  });

export const fetchRadar = (list?: string) =>
  request<RadarCard[]>(`/radar${list ? `?list=${list}` : ""}`);

export interface UploadResult {
  tender_id: string;
  document_id: string;
  status: string;
}

// Manual tender upload (US-03). Multipart — do not set Content-Type by hand.
export async function uploadTender(file: File): Promise<UploadResult> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${API_BASE}/tenders/upload`, {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  return response.json();
}

export interface DiscoveryRunResult {
  runs: {
    adapter: string;
    ok: boolean;
    error: string | null;
    discovered: number;
    ingested: number;
    duplicates: number;
  }[];
}

// Run the Scout now — scrape the portal adapters (US-01).
export const runDiscovery = () =>
  request<DiscoveryRunResult>(`/discovery/run`, { method: "POST" });

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
    headers: authHeaders(),
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
    headers: authHeaders(),
  });
  if (!response.ok) throw new Error(`${response.status}`);
  return response.arrayBuffer();
}

export async function fetchDocumentBlobById(
  documentId: string,
): Promise<ArrayBuffer> {
  const response = await fetch(`${API_BASE}/documents/${documentId}/file`, {
    headers: authHeaders(),
  });
  if (!response.ok) throw new Error(`${response.status}`);
  return response.arrayBuffer();
}

// --- Onboarding wizard (US-17) -------------------------------------------

export interface OnboardingStatus {
  org_id: string;
  name: string;
  slug: string;
  steps: {
    org: boolean;
    facts: boolean;
    products: boolean;
    profile: boolean;
    branding: boolean;
  };
  facts: number;
  products: number;
  onboarded: boolean;
  ready: boolean;
}

// Creating the org is the one open step — it precedes having an org id, so it
// deliberately does not carry the org header.
export async function createOrg(
  name: string,
  slug: string,
): Promise<{ org_id: string; name: string; slug: string }> {
  const response = await fetch(`${API_BASE}/onboarding/org`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, slug }),
  });
  if (response.status === 409) throw new Error(`slug '${slug}' is already taken`);
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  return response.json();
}

async function uploadCsv(
  path: string,
  csv: string,
  filename: string,
): Promise<Response> {
  const form = new FormData();
  form.append("file", new Blob([csv], { type: "text/csv" }), filename);
  return fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
}

export async function uploadFactsCsv(csv: string): Promise<number> {
  const r = await uploadCsv("/onboarding/facts", csv, "facts.csv");
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return (await r.json()).facts_loaded as number;
}

export async function uploadProductsCsv(csv: string): Promise<number> {
  const r = await uploadCsv("/onboarding/products", csv, "products.csv");
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return (await r.json()).products_loaded as number;
}

export const saveOnboardingProfile = (profile: {
  categories: { name: string; keywords: string[] }[];
  weights: Record<string, number>;
  value_band_inr: { min_inr?: number; max_inr?: number };
  locations: string[];
  win_categories: string[];
}) =>
  request<{ profile: string }>(`/onboarding/profile`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(profile),
  });

export const saveBranding = (branding: {
  primary_color?: string;
  logo_url?: string;
  finish: boolean;
}) =>
  request<{ branding: string; onboarded: boolean }>(`/onboarding/branding`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(branding),
  });

export const fetchOnboardingStatus = () =>
  request<OnboardingStatus>(`/onboarding/status`);

export const FACTS_CSV_TEMPLATE_URL = `${API_BASE}/onboarding/templates/facts.csv`;
export const PRODUCTS_CSV_TEMPLATE_URL = `${API_BASE}/onboarding/templates/products.csv`;
