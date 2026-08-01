// The Model Comparison Lab (US-14, SPEC screen 7): the same gold set scored
// across models — F1 per family, exact numbers, hallucination, citation,
// speed, ₹/tender. Adopting the winner is a config change, not code.
import { Reveal } from "../ui/motion";
import { Scale, TriangleAlert } from "lucide-react";
import { EmptyState } from "../ui/primitives";
import type { LeaderboardRow, ModelLabResult } from "../api";

function bar(pct: number, color: string) {
  return (
    <div className="h-2 w-full rounded-[8px] bg-surface">
      <div
        className={`h-2 rounded-[8px] ${color}`}
        style={{ width: `${Math.round(pct * 100)}%` }}
      />
    </div>
  );
}

export function ModelLab({
  result,
  onRun,
  busy,
}: {
  result: ModelLabResult | null;
  onRun: () => void;
  busy: boolean;
}) {
  const winner: LeaderboardRow | undefined = result?.leaderboard[0];

  return (
    <div className="mx-auto max-w-4xl p-6">
      <div className="mb-4 flex items-center gap-3">
        <h1 className="text-xl font-semibold tracking-[-0.01em] text-ink">Model Lab</h1>
        {result && (
          <span className="text-xs text-ink-subtle">
            same gold set ({result.gold_tenders} tenders) · role: {result.role}
          </span>
        )}
        <button
          onClick={onRun}
          disabled={busy}
          className="ml-auto rounded-[8px] bg-indigo px-3 py-1.5 text-sm font-medium text-white transition-colors duration-150 hover:bg-indigo-active disabled:opacity-50"
        >
          {busy ? "Running…" : "Run leaderboard"}
        </button>
      </div>

      {!result && (
        <EmptyState
          icon={<Scale size={40} strokeWidth={1.25} className="text-ink-subtle" />}
          title="No leaderboard yet"
          body="Run the same gold set through every model and compare accuracy, speed and cost. Because every call goes through the gateway's small/mid/strong roles, adopting the winner is a config change rather than code."
        />
      )}

      {/* The honesty banner, in the same shape Analytics uses for an
          uncalibrated metric. This used to be eleven grey pixels reading
          "· simulated profiles" beside the title, which is not a disclosure —
          it is a place to point at afterwards. These rows come from
          `services/modellab.py::_simulate`; no model is called. Someone
          discovering that mid-demo is far worse than reading it here. */}
      {result?.simulated && (
        <div
          data-testid="modellab-simulated"
          className="mb-3 flex gap-2 rounded-[8px] border border-dashed border-warning/40 bg-warning-tint px-3 py-2 text-xs text-warning"
        >
          <TriangleAlert size={14} strokeWidth={2} aria-hidden className="mt-px shrink-0" />
          <span>
            <span className="font-medium">These scores are simulated. </span>
            The comparison harness runs, but the per-model figures come from
            profiles rather than from real calls through the gateway. Treat this
            as the shape of the answer, not the answer.
          </span>
        </div>
      )}

      {result && (
        <>
          {winner && (
            <div className="mb-3 rounded-[12px] border border-success/25 bg-success-tint p-3 text-sm text-success">
              Winner by F1: <strong>{winner.model}</strong> — F1{" "}
              {winner.f1_overall} · hallucination {winner.hallucination_rate} ·
              ₹{winner.cost_per_tender_inr}/tender
            </div>
          )}
          <Reveal className="overflow-x-auto rounded-[12px] border border-hairline bg-white shadow-card">
            <table className="w-full text-left text-xs" data-testid="leaderboard">
              <thead className="bg-surface text-ink-subtle">
                <tr>
                  <th className="px-3 py-2">Model</th>
                  <th className="px-3 py-2">F1 (overall)</th>
                  <th className="px-3 py-2">F1 (eligibility)</th>
                  <th className="px-3 py-2">Exact #</th>
                  <th className="px-3 py-2">Halluc.</th>
                  <th className="px-3 py-2">Citation</th>
                  <th className="px-3 py-2">Speed</th>
                  <th className="px-3 py-2">₹/tender</th>
                </tr>
              </thead>
              <tbody>
                {result.leaderboard.map((row) => (
                  <tr key={row.model} data-testid="lab-row" className="border-t border-hairline">
                    <td className="px-3 py-2">
                      <div className="font-medium text-ink">{row.model}</div>
                      <div className="text-[11px] text-ink-subtle">{row.kind}</div>
                    </td>
                    <td className="px-3 py-2">
                      <div className="mb-1 font-mono">{row.f1_overall}</div>
                      {bar(row.f1_overall, "bg-success")}
                    </td>
                    <td className="px-3 py-2 font-mono">{row.f1_eligibility}</td>
                    <td className="px-3 py-2 font-mono">
                      {row.exact_numbers ?? "—"}
                    </td>
                    <td className="px-3 py-2 font-mono">{row.hallucination_rate}</td>
                    <td className="px-3 py-2 font-mono">{row.citation_complete}</td>
                    <td className="px-3 py-2 font-mono">{row.speed_ms} ms</td>
                    <td className="px-3 py-2 font-mono">₹{row.cost_per_tender_inr}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Reveal>
        </>
      )}
    </div>
  );
}
