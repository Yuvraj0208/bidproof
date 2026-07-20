// Proposal Studio (US-09): the draft, section by section, with a per-claim
// badge (verified / cannot-verify / contradicted) and each section's
// verified-% chip. Facts come only from the capability DB; the TipTap editor
// and section-by-section approval land in US-11.
import type { Proposal, ProposalClaim } from "../api";

const CLAIM_STYLE: Record<ProposalClaim["status"], string> = {
  verified: "bg-emerald-100 text-emerald-800",
  cannot_verify: "bg-amber-100 text-amber-800",
  contradicted: "bg-red-100 text-red-800",
};

const CLAIM_LABEL: Record<ProposalClaim["status"], string> = {
  verified: "verified",
  cannot_verify: "cannot verify",
  contradicted: "contradicted",
};

function pctBand(pct: number | null): string {
  if (pct == null) return "bg-slate-100 text-slate-500";
  if (pct >= 90) return "bg-emerald-100 text-emerald-800";
  if (pct >= 50) return "bg-amber-100 text-amber-800";
  return "bg-red-100 text-red-800";
}

export function ProposalPanel({
  proposal,
  onGenerate,
  busy,
}: {
  proposal: Proposal | null;
  onGenerate: () => void;
  busy: boolean;
}) {
  return (
    <div className="mx-auto max-w-2xl space-y-4 p-6">
      <div className="flex items-center gap-3">
        <h2 className="text-sm font-semibold text-slate-800">Proposal draft</h2>
        {proposal?.duration_ms != null && (
          <span className="text-xs text-slate-400">
            drafted in {(proposal.duration_ms / 1000).toFixed(1)}s ·{" "}
            {proposal.format_source.replace("_", " ")}
          </span>
        )}
        <button
          onClick={onGenerate}
          disabled={busy}
          className="ml-auto rounded border px-2 py-1 text-sm text-slate-600 hover:bg-slate-50 disabled:opacity-50"
        >
          {busy ? "Drafting…" : proposal ? "Re-draft" : "Draft proposal"}
        </button>
      </div>

      {!proposal && (
        <p className="text-sm text-slate-500">
          No draft yet. A proposal can be drafted once the decision is GO — every
          factual sentence is grounded in your capability database.
        </p>
      )}

      {proposal?.sections.map((section) => (
        <article
          key={section.id}
          data-testid="proposal-section"
          className="rounded-lg border bg-white p-4"
        >
          <div className="mb-2 flex items-center gap-2">
            <span className="text-sm font-medium text-slate-800">
              {section.section_tag.replace(/_/g, " ")}
            </span>
            <span
              data-testid="verified-chip"
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${pctBand(section.verified_pct)}`}
            >
              {section.verified_pct == null
                ? "no claims"
                : `${section.verified_pct}% verified`}
            </span>
            {section.dropped_untagged > 0 && (
              <span className="rounded bg-red-50 px-1.5 text-[11px] text-red-600">
                {section.dropped_untagged} ungrounded dropped
              </span>
            )}
          </div>
          <pre className="whitespace-pre-wrap rounded bg-slate-50 p-3 text-xs text-slate-700">
            {section.content}
          </pre>
          {section.claims.length > 0 && (
            <ul className="mt-2 space-y-1">
              {section.claims.map((claim, i) => (
                <li
                  key={i}
                  data-testid="claim"
                  className="flex items-start gap-2 text-xs"
                >
                  <span
                    className={`shrink-0 rounded px-1.5 ${CLAIM_STYLE[claim.status]}`}
                  >
                    {CLAIM_LABEL[claim.status]}
                  </span>
                  <span className="text-slate-600">
                    {claim.text}
                    {claim.source_tag && (
                      <span className="ml-1 font-mono text-slate-400">
                        {claim.source_tag}
                      </span>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </article>
      ))}
    </div>
  );
}
