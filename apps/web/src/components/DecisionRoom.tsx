// The Decision Room (US-06): EV maths term by term in rupees, the hard
// gate, top risks — and Checkpoint 4: a named human signs off or overrides
// with a written reason. No approve-all, no auto-pass.
import { useState } from "react";
import { ConfidenceChip } from "./ConfidenceChip";

export interface EvTerm {
  key: string;
  label: string;
  formula: string;
  value_inr: number;
}

export interface DecisionData {
  recommendation: string;
  ev_inr: number | null;
  terms: EvTerm[];
  gate_failed: { key: string }[];
  confidence: number;
  band: "green" | "yellow" | "red";
  reason: string;
  status: string;
  signed_off_by: string | null;
}

export interface BriefRisk {
  code: string;
  severity: string;
  message: string;
  rupee_impact: number | null;
}

const inr = (value: number) =>
  `${value < 0 ? "−" : ""}₹${(Math.abs(value) / 1e5).toFixed(2)} lakh`;

const REC_STYLE: Record<string, string> = {
  go: "bg-emerald-100 text-emerald-800",
  no_go: "bg-red-100 text-red-800",
  needs_human: "bg-amber-100 text-amber-800",
};

export function DecisionRoom({
  decision,
  risks,
  onSignOff,
  onOverride,
}: {
  decision: DecisionData | null;
  risks: BriefRisk[];
  onSignOff: (name: string) => void;
  onOverride: (name: string, recommendation: string, reason: string) => void;
}) {
  const [name, setName] = useState("");
  const [overrideReason, setOverrideReason] = useState("");

  if (!decision) {
    return (
      <p className="p-6 text-sm text-slate-500">
        No decision yet — run the check, then compute the EV.
      </p>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <section className="flex items-center gap-3">
        <span
          data-testid="recommendation"
          className={`rounded px-3 py-1 text-sm font-semibold uppercase ${REC_STYLE[decision.recommendation] ?? ""}`}
        >
          {decision.recommendation.replace("_", " ")}
        </span>
        {decision.ev_inr != null && (
          <span className="text-lg font-semibold text-slate-900">
            EV {inr(decision.ev_inr)}
          </span>
        )}
        <ConfidenceChip
          confidence={decision.confidence}
          band={decision.band}
          reason={decision.reason}
        />
        <span className="ml-auto text-xs text-slate-400">
          {decision.status === "pending_signoff"
            ? "awaiting sign-off (checkpoint 4)"
            : `${decision.status} by ${decision.signed_off_by}`}
        </span>
      </section>

      {decision.gate_failed.length > 0 && (
        <section className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          Hard gate: mandatory eligibility failed —{" "}
          {decision.gate_failed.map((g) => g.key).join(", ")}. EV not computed.
        </section>
      )}

      {decision.terms.length > 0 && (
        <table className="w-full text-sm" data-testid="ev-terms">
          <tbody>
            {decision.terms.map((term) => (
              <tr key={term.key} className="border-b align-top">
                <td className="py-2 pr-3">
                  <div className="font-medium text-slate-800">{term.label}</div>
                  <div className="text-xs text-slate-500">{term.formula}</div>
                </td>
                <td className="py-2 text-right font-mono text-sm">
                  {inr(term.value_inr)}
                </td>
              </tr>
            ))}
            {decision.ev_inr != null && (
              <tr className="font-semibold">
                <td className="py-2">Expected value</td>
                <td className="py-2 text-right font-mono">{inr(decision.ev_inr)}</td>
              </tr>
            )}
          </tbody>
        </table>
      )}

      {risks.length > 0 && (
        <section>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Top risks
          </h2>
          <ul className="space-y-1 text-sm">
            {risks.map((risk) => (
              <li key={risk.code} className="flex gap-2">
                <span
                  className={`rounded px-1.5 text-xs ${
                    risk.severity === "high"
                      ? "bg-red-100 text-red-700"
                      : "bg-amber-100 text-amber-700"
                  }`}
                >
                  {risk.severity}
                </span>
                <span className="text-slate-600">{risk.message}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {decision.status === "pending_signoff" && (
        <section className="space-y-2 rounded border bg-slate-50 p-4">
          <label className="block text-xs font-medium text-slate-600">
            Checkpoint 4 — a named human signs this decision
          </label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Your name"
            className="w-full rounded border px-2 py-1 text-sm"
          />
          <div className="flex gap-2">
            <button
              data-testid="signoff-button"
              disabled={name.trim().length < 2}
              onClick={() => onSignOff(name.trim())}
              className="rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40"
            >
              Sign off {decision.recommendation.replace("_", " ")}
            </button>
          </div>
          <div className="pt-2">
            <input
              value={overrideReason}
              onChange={(e) => setOverrideReason(e.target.value)}
              placeholder="Override reason (required, logged)"
              className="w-full rounded border px-2 py-1 text-sm"
            />
            <button
              data-testid="override-button"
              disabled={name.trim().length < 2 || overrideReason.trim().length < 5}
              onClick={() =>
                onOverride(
                  name.trim(),
                  decision.recommendation === "go" ? "no_go" : "go",
                  overrideReason.trim(),
                )
              }
              className="mt-1 rounded border px-3 py-1.5 text-sm text-slate-600 disabled:opacity-40"
            >
              Override to {decision.recommendation === "go" ? "NO GO" : "GO"}
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
