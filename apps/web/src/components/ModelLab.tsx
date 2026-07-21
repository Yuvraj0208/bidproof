// The Model Comparison Lab (US-14, SPEC screen 7): the same gold set scored
// across models — F1 per family, exact numbers, hallucination, citation,
// speed, ₹/tender. Adopting the winner is a config change, not code.
import type { LeaderboardRow, ModelLabResult } from "../api";

function bar(pct: number, color: string) {
  return (
    <div className="h-2 w-full rounded bg-slate-100">
      <div
        className={`h-2 rounded ${color}`}
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
        <h1 className="text-lg font-semibold text-indigo-900">Model Lab</h1>
        {result && (
          <span className="text-xs text-slate-400">
            same gold set ({result.gold_tenders} tenders) · role: {result.role}
            {result.simulated ? " · simulated profiles" : ""}
          </span>
        )}
        <button
          onClick={onRun}
          disabled={busy}
          className="ml-auto rounded bg-indigo-600 px-3 py-1 text-sm font-medium text-white disabled:opacity-50"
        >
          {busy ? "Running…" : "Run leaderboard"}
        </button>
      </div>

      {!result && (
        <p className="text-sm text-slate-500">
          Run the same gold set through every model and compare accuracy, speed,
          and cost. The winner can be adopted as a config change.
        </p>
      )}

      {result && (
        <>
          {winner && (
            <div className="mb-3 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">
              Winner by F1: <strong>{winner.model}</strong> — F1{" "}
              {winner.f1_overall} · hallucination {winner.hallucination_rate} ·
              ₹{winner.cost_per_tender_inr}/tender
            </div>
          )}
          <div className="overflow-x-auto rounded-lg border bg-white">
            <table className="w-full text-left text-xs" data-testid="leaderboard">
              <thead className="bg-slate-50 text-slate-500">
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
                  <tr key={row.model} data-testid="lab-row" className="border-t">
                    <td className="px-3 py-2">
                      <div className="font-medium text-slate-800">{row.model}</div>
                      <div className="text-[11px] text-slate-400">{row.kind}</div>
                    </td>
                    <td className="px-3 py-2">
                      <div className="mb-1 font-mono">{row.f1_overall}</div>
                      {bar(row.f1_overall, "bg-emerald-500")}
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
          </div>
          {result.simulated && (
            <p className="mt-2 text-[11px] text-slate-400">
              Profiles are simulated until API keys are configured; the scoring
              is real and swapping in a live model is a config change.
            </p>
          )}
        </>
      )}
    </div>
  );
}
