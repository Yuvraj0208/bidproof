// The Agent Console (US-12): every agent call under the tender's trace id,
// and the totals line that is the whole business case —
// "5 agent calls · 12,300 tokens · ₹38.40 · 6.2 s" vs two man-days.
export interface AgentRunData {
  id: string;
  agent: string;
  status: string;
  model_role: string | null;
  prompt_version: string | null;
  tokens_in: number;
  tokens_out: number;
  cost_inr: number;
  duration_ms: number;
  meta: Record<string, unknown>;
  created_at: string;
}

export interface ConsoleTotals {
  calls: number;
  tokens: number;
  cost_inr: number;
  duration_ms: number;
}

export function totalsLine(totals: ConsoleTotals): string {
  const seconds = (totals.duration_ms / 1000).toFixed(1);
  return `${totals.calls} agent calls · ${totals.tokens.toLocaleString("en-IN")} tokens · ₹${totals.cost_inr.toFixed(2)} · ${seconds} s`;
}

export function AgentConsole({
  runs,
  totals,
  onReplay,
  replaying,
}: {
  runs: AgentRunData[];
  totals: ConsoleTotals | null;
  onReplay: () => void;
  replaying: boolean;
}) {
  if (runs.length === 0) {
    return (
      <p className="p-6 text-sm text-ink-muted">
        No agent runs recorded yet for this tender.
      </p>
    );
  }
  return (
    <div className="mx-auto max-w-3xl p-6">
      <div className="mb-4 flex items-center gap-3">
        <span
          data-testid="totals-line"
          data-numeric
          className="rounded-[8px] bg-indigo-tint px-3 py-1.5 text-sm font-medium text-indigo"
        >
          {totals ? totalsLine(totals) : ""}
        </span>
        <button
          onClick={onReplay}
          disabled={replaying}
          className="ml-auto rounded-[8px] border border-hairline px-2 py-1 text-sm text-ink-muted transition-colors duration-150 hover:bg-indigo-tint disabled:opacity-50"
        >
          {replaying ? "Replaying…" : "Replay run"}
        </button>
      </div>
      <ol className="space-y-2">
        {runs.map((run) => (
          <li
            key={run.id}
            data-testid="agent-run"
            className="rounded-[12px] border border-hairline bg-white p-3 shadow-card transition-shadow duration-150 hover:shadow-overlay"
          >
            <div className="flex items-center gap-2 text-sm">
              <span className="font-mono font-medium text-ink">
                {run.agent}
              </span>
              {run.model_role && (
                <span className="rounded-[8px] bg-surface px-1.5 text-xs text-ink-muted">
                  role: {run.model_role}
                </span>
              )}
              {run.prompt_version && (
                <span className="rounded-[8px] bg-surface px-1.5 text-xs text-ink-muted">
                  {run.prompt_version}
                </span>
              )}
              {run.status !== "ok" && (
                <span className="rounded-[8px] bg-danger-tint px-1.5 text-xs text-danger">
                  {run.status}
                </span>
              )}
              <span className="ml-auto text-xs text-ink-subtle">
                {run.tokens_in + run.tokens_out} tok · ₹{run.cost_inr.toFixed(2)} ·{" "}
                {run.duration_ms} ms
              </span>
            </div>
            <div className="mt-1 truncate font-mono text-[11px] text-ink-subtle">
              {JSON.stringify(run.meta)}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
