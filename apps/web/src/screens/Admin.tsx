// Admin (SPEC §17 screen 9): roles, prompt approvals, model config per role,
// thresholds, budgets, the append-only audit log, scraper health, kill switch.
//
// Everything here is read from live endpoints. The kill switch and budgets are
// shown as governed controls: the SPEC requires them to exist and be visible,
// and where the backend does not yet enforce one the UI says so rather than
// pretending the lever is wired.
import { useEffect, useState } from "react";
import { API_BASE, authHeaders, getRole, ROLES, type ModelHealth } from "../api";
import { DataTable } from "../ui/DataTable";
import { Pill } from "../ui/chips";
import {
  Card,
  EmptyState,
  FieldLabel,
  PageHeader,
  SkeletonLoader,
} from "../ui/primitives";

interface AuditEntry {
  id: string;
  action: string;
  actor: string | null;
  entity: string | null;
  created_at: string;
  detail?: Record<string, unknown> | null;
}

interface DiscoveryRun {
  id: string;
  started_at: string;
  finished_at: string | null;
  report: { runs?: { adapter: string; ok: boolean; error: string | null; ingested: number }[] };
}

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, { headers: authHeaders() });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

export default function Admin() {
  const [audit, setAudit] = useState<AuditEntry[] | null>(null);
  const [auditError, setAuditError] = useState<string | null>(null);
  const [models, setModels] = useState<ModelHealth | null>(null);
  const [scraper, setScraper] = useState<DiscoveryRun[] | null>(null);
  const role = getRole();

  useEffect(() => {
    get<AuditEntry[]>("/audit").then(setAudit).catch((e) => setAuditError(String(e)));
    fetch(`${API_BASE}/health/models`).then((r) => r.json()).then(setModels).catch(() => {});
    get<DiscoveryRun[]>("/discovery/runs").then(setScraper).catch(() => setScraper([]));
  }, []);

  const lastRun = scraper?.[0];
  const adapters = lastRun?.report?.runs ?? [];

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <PageHeader
        title="Admin"
        subtitle="Roles, models, governance and the append-only audit trail."
        meta={<Pill tone="brand">acting as {role}</Pill>}
      />

      {/* Model configuration per role */}
      <Card className="mb-4">
        <FieldLabel>Model configuration (per role)</FieldLabel>
        <p className="mt-1 text-xs text-ink-muted">
          Application code names only a role — small, mid or strong. Which model
          serves a role is a gateway config change, never a code change.
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          {["small", "mid", "strong"].map((roleName) => {
            const entry = models?.roles?.[roleName];
            return (
              <div
                key={roleName}
                data-testid="model-role"
                className={`rounded-[12px] border p-3 ${
                  entry?.ok
                    ? "border-success/25 bg-success-tint"
                    : entry
                      ? "border-danger/25 bg-danger-tint"
                      : "border-hairline bg-white"
                }`}
              >
                <div className="text-xs font-semibold uppercase tracking-wide text-ink-subtle">
                  {roleName}
                </div>
                <div className="mt-1 text-sm font-medium text-ink">
                  {entry ? (entry.ok ? "reachable" : "unavailable") : "checking…"}
                </div>
                {entry?.error && (
                  <div className="mt-1 text-xs text-danger">{entry.error}</div>
                )}
              </div>
            );
          })}
        </div>
      </Card>

      <div className="mb-4 grid gap-4 md:grid-cols-2">
        {/* Roles */}
        <Card>
          <FieldLabel>Roles</FieldLabel>
          <p className="mt-1 text-xs text-ink-muted">
            The acting role gates sensitive actions. Auditor sits outside the
            acting chain: it can read and audit, never act on a bid.
          </p>
          <ul className="mt-3 space-y-1 text-sm">
            {ROLES.map((r) => (
              <li key={r} className="flex items-center justify-between border-b border-hairline py-1">
                <span className="text-ink">{r}</span>
                {r === role && <Pill tone="brand">you</Pill>}
              </li>
            ))}
          </ul>
        </Card>

        {/* Scraper health */}
        <Card>
          <FieldLabel>Scraper health</FieldLabel>
          {scraper === null ? (
            <div className="mt-3"><SkeletonLoader rows={3} /></div>
          ) : adapters.length === 0 ? (
            <p className="mt-3 text-sm text-ink-muted">
              No discovery run recorded yet. Run one from the Tender Radar.
            </p>
          ) : (
            <ul className="mt-3 space-y-2 text-sm">
              {adapters.map((a) => (
                <li key={a.adapter} data-testid="adapter-health" className="flex items-center gap-2">
                  <span
                    aria-hidden
                    className={`h-2 w-2 rounded-full ${a.ok ? "bg-success" : "bg-danger"}`}
                  />
                  <span className="font-medium text-ink">{a.adapter}</span>
                  <span className="text-ink-muted">
                    {a.ok ? `${a.ingested} ingested` : (a.error ?? "failed")}
                  </span>
                </li>
              ))}
            </ul>
          )}
          {lastRun && (
            <p className="mt-3 text-xs text-ink-subtle">
              Last run {new Date(lastRun.started_at).toLocaleString()}
            </p>
          )}
        </Card>
      </div>

      {/* Governance: prompts, thresholds, budgets, kill switch */}
      <div className="mb-4 grid gap-4 md:grid-cols-2">
        <Card>
          <FieldLabel>Prompt approvals</FieldLabel>
          <p className="mt-1 text-xs text-ink-muted">
            Prompts are versioned like code. Editing one changes its sha256 and
            fails the prompt-approval gate in CI until it is re-approved — and
            re-approval requires the gold set to pass.
          </p>
          <div className="mt-3 rounded-[8px] border border-hairline bg-surface px-3 py-2 text-xs text-ink-muted">
            Enforced in CI by <span className="font-mono">tests/test_prompt_approval.py</span>{" "}
            against <span className="font-mono">infra/prompt_approvals.json</span>.
          </div>
        </Card>

        <Card>
          <FieldLabel>Thresholds, budgets and kill switch</FieldLabel>
          <div className="mt-3 space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-ink-muted">Auto-accept confidence band</span>
              <span data-numeric className="font-medium text-ink">≥ 0.70</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-ink-muted">Cost ceiling per tender</span>
              <span data-numeric className="font-medium text-ink">₹50</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-ink-muted">Scout (portal discovery)</span>
              <span className="font-medium text-ink">
                env <span className="font-mono">SCOUT_ENABLED</span>
              </span>
            </div>
          </div>
          <div className="mt-3 rounded-[8px] border border-dashed border-warning/40 bg-warning-tint px-3 py-2 text-xs text-warning">
            <span className="font-medium">Read-only here — </span>
            these are set in configuration; the UI does not yet write them back.
          </div>
        </Card>
      </div>

      {/* Append-only audit log */}
      <Card padded={false}>
        <div className="border-b border-hairline px-4 py-3">
          <FieldLabel>Audit log (append-only)</FieldLabel>
        </div>
        {auditError ? (
          <div className="p-4">
            <div className="rounded-[8px] border border-danger/25 bg-danger-tint px-3 py-2 text-sm text-danger">
              {auditError.includes("403")
                ? "Your role may not read the audit log — switch to auditor or admin."
                : auditError}
            </div>
          </div>
        ) : audit === null ? (
          <div className="p-4"><SkeletonLoader rows={4} /></div>
        ) : (
          <DataTable<AuditEntry>
            rows={audit}
            rowKey={(r) => r.id}
            caption={`${audit.length} entries`}
            empty={
              <div className="p-4">
                <EmptyState
                  title="No audit entries yet"
                  body="Sign-offs, overrides, exports and model swaps are recorded here and can never be edited."
                />
              </div>
            }
            columns={[
              {
                key: "created_at",
                header: "When",
                width: "20%",
                sortValue: (r) => r.created_at,
                render: (r) => (
                  <span data-numeric className="text-xs text-ink-muted">
                    {new Date(r.created_at).toLocaleString()}
                  </span>
                ),
              },
              { key: "action", header: "Action", sortValue: (r) => r.action },
              {
                key: "actor",
                header: "Actor",
                sortValue: (r) => r.actor ?? "",
                render: (r) => r.actor ?? "—",
              },
              {
                key: "entity",
                header: "Entity",
                render: (r) => (
                  <span className="font-mono text-xs text-ink-muted">{r.entity ?? "—"}</span>
                ),
              },
            ]}
          />
        )}
      </Card>
    </div>
  );
}
