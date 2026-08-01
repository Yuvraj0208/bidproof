// The Decision Room (US-06): EV maths term by term in rupees, the hard
// gate, top risks — and Checkpoint 4: a named human signs off or overrides
// with a written reason. No approve-all, no auto-pass.
import { Reveal } from "../ui/motion";
import { useState } from "react";
import { ConfidenceChip } from "./ConfidenceChip";
import { LedgerArt } from "../ui/artwork";
import { RiskTag } from "../ui/chips";
import { Card, EmptyState, FieldLabel, StatCallout } from "../ui/primitives";

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
  go: "bg-success-tint text-success",
  no_go: "bg-danger-tint text-danger",
  needs_human: "bg-warning-tint text-warning",
};

export function DecisionRoom({
  decision,
  risks,
  onSignOff,
  onOverride,
  canSignOff = true,
  roleNote,
}: {
  decision: DecisionData | null;
  risks: BriefRisk[];
  onSignOff: (name: string) => void;
  onOverride: (name: string, recommendation: string, reason: string) => void;
  // Checkpoint 4 is Bid-Head-and-above only. When the acting role can't sign,
  // the controls are disabled and the requirement is shown (never silent).
  canSignOff?: boolean;
  roleNote?: string;
}) {
  const [name, setName] = useState("");
  const [overrideReason, setOverrideReason] = useState("");

  if (!decision) {
    return (
      <div className="p-6">
        <EmptyState
          title="No decision yet"
          body="Run the compliance check, then compute the expected value. The maths is shown term by term so it can be argued with."
          icon={<LedgerArt />}
        />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <Reveal>
      <Card className="border-indigo/15 bg-indigo-tint/40">
        <div className="flex flex-wrap items-center gap-3">
          <span
            data-testid="recommendation"
            className={`rounded-[8px] px-3 py-1 text-sm font-semibold uppercase ${REC_STYLE[decision.recommendation] ?? ""}`}
          >
            {decision.recommendation.replace("_", " ")}
          </span>
          <ConfidenceChip
            confidence={decision.confidence}
            band={decision.band}
            reason={decision.reason}
          />
          <span className="ml-auto text-xs text-ink-subtle">
            {decision.status === "pending_signoff"
              ? "awaiting sign-off (checkpoint 4)"
              : // `signed_off` is a database value; it was reaching the screen
                // verbatim, underscore and all.
                `${decision.status.replace(/_/g, " ")} by ${decision.signed_off_by}`}
          </span>
        </div>
        {decision.ev_inr != null && (
          <div className="mt-4">
            <StatCallout
              label="Expected value"
              value={inr(decision.ev_inr)}
              hint={decision.reason}
              tone={decision.ev_inr >= 0 ? "success" : "danger"}
              size="lg"
            />
          </div>
        )}
      </Card>
      </Reveal>

      {decision.gate_failed.length > 0 && (
        <section className="rounded-[12px] border border-danger/25 bg-danger-tint p-3 text-sm text-danger">
          Hard gate: mandatory eligibility failed —{" "}
          {decision.gate_failed.map((g) => g.key).join(", ")}. EV not computed.
        </section>
      )}

      {decision.terms.length > 0 && (
        <table className="w-full text-sm" data-testid="ev-terms">
          <tbody>
            {decision.terms.map((term) => (
              <tr key={term.key} className="border-b border-hairline align-top">
                <td className="py-2 pr-3">
                  <div className="font-medium text-ink">{term.label}</div>
                  <div className="text-xs text-ink-muted">{term.formula}</div>
                </td>
                <td data-numeric className="py-2 text-right text-sm font-medium">
                  {inr(term.value_inr)}
                </td>
              </tr>
            ))}
            {decision.ev_inr != null && (
              // The total is the line the whole screen exists to produce, and
              // it was set in the same weight as the terms above it. It gets a
              // rule and a size, the way a figure you sign off on should read.
              <tr className="border-t-2 border-ink/15">
                <td className="pt-3 text-[15px] font-semibold text-ink">
                  Expected value
                </td>
                <td
                  data-numeric
                  className={`pt-3 text-right text-lg font-semibold tracking-[-0.02em] ${
                    decision.ev_inr >= 0 ? "text-success" : "text-danger"
                  }`}
                >
                  {inr(decision.ev_inr)}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}

      {risks.length > 0 && (
        <section>
          <FieldLabel>Risk register</FieldLabel>
          <ul className="mt-2 space-y-2 text-sm">
            {risks.map((risk) => (
              <li key={risk.code} className="flex flex-wrap items-center gap-2">
                <RiskTag
                  label={risk.code.replace(/_/g, " ")}
                  impactInr={(risk as { impact_inr?: number | null }).impact_inr ?? null}
                  severity={risk.severity === "high" ? "high" : "medium"}
                />
                <span className="text-ink-muted">{risk.message}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {decision.status === "pending_signoff" && (
        <section className="space-y-2 rounded-[12px] border border-hairline bg-white p-4 shadow-card">
          <label className="block text-xs font-medium text-ink-muted">
            Checkpoint 4 — a named human signs this decision
          </label>
          {!canSignOff && roleNote && (
            <p
              data-testid="role-gate-note"
              className="rounded-[8px] bg-warning-tint px-2 py-1 text-xs text-warning"
            >
              {roleNote}
            </p>
          )}
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Your name"
            disabled={!canSignOff}
            className="w-full rounded-[8px] border border-hairline px-2 py-1 text-sm disabled:bg-surface"
          />
          <div className="flex gap-2">
            <button
              data-testid="signoff-button"
              disabled={!canSignOff || name.trim().length < 2}
              onClick={() => onSignOff(name.trim())}
              className="rounded-[8px] bg-indigo px-3 py-1.5 text-sm font-medium text-white transition-colors duration-150 hover:bg-indigo-active disabled:opacity-40"
            >
              Sign off {decision.recommendation.replace("_", " ")}
            </button>
          </div>
          <div className="pt-2">
            <input
              value={overrideReason}
              onChange={(e) => setOverrideReason(e.target.value)}
              placeholder="Override reason (required, logged)"
              disabled={!canSignOff}
              className="w-full rounded-[8px] border border-hairline px-2 py-1 text-sm disabled:bg-surface"
            />
            <button
              data-testid="override-button"
              disabled={!canSignOff || name.trim().length < 2 || overrideReason.trim().length < 5}
              onClick={() =>
                onOverride(
                  name.trim(),
                  decision.recommendation === "go" ? "no_go" : "go",
                  overrideReason.trim(),
                )
              }
              className="mt-1 rounded-[8px] border border-hairline px-3 py-1.5 text-sm text-ink-muted transition-colors duration-150 hover:bg-indigo-tint disabled:opacity-40"
            >
              Override to {decision.recommendation === "go" ? "NO GO" : "GO"}
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
