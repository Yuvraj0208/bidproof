// Proposal Studio (US-09 + US-11): the draft, section by section, with a
// per-claim badge, three per-section scores, and INDIVIDUAL approval —
// there is deliberately no "approve all" button, and a section with an open
// flag cannot be approved until it is resolved.
import { useState } from "react";
import type { Proposal, ProposalClaim, ProposalSection } from "../api";

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

function scoreBand(pct: number | null): string {
  if (pct == null) return "bg-slate-100 text-slate-500";
  if (pct >= 90) return "bg-emerald-100 text-emerald-800";
  if (pct >= 50) return "bg-amber-100 text-amber-800";
  return "bg-red-100 text-red-800";
}

function Score({ label, pct }: { label: string; pct: number | null }) {
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${scoreBand(pct)}`}
    >
      {label} {pct == null ? "n/a" : `${pct}%`}
    </span>
  );
}

export function ProposalPanel({
  proposal,
  onGenerate,
  onApprove,
  busy,
}: {
  proposal: Proposal | null;
  onGenerate: () => void;
  onApprove: (sectionId: string, name: string) => void;
  busy: boolean;
}) {
  const [name, setName] = useState("");
  const approvedCount = proposal?.sections.filter((s) => s.approved).length ?? 0;
  const ready =
    proposal != null &&
    proposal.sections.length > 0 &&
    approvedCount === proposal.sections.length;

  const canApprove = (section: ProposalSection) =>
    name.trim().length >= 2 && !section.approved && section.open_flags.length === 0;

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-6">
      <div className="flex items-center gap-3">
        <h2 className="text-sm font-semibold text-slate-800">Proposal draft</h2>
        {proposal && (
          <span
            data-testid="approval-progress"
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${ready ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}`}
          >
            {ready
              ? "all sections approved"
              : `${approvedCount}/${proposal.sections.length} sections approved`}
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

      {proposal && (
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Your name (to approve sections)"
          className="w-full rounded border px-2 py-1 text-sm"
        />
      )}

      {proposal?.sections.map((section) => (
        <article
          key={section.id}
          data-testid="proposal-section"
          className={`rounded-lg border bg-white p-4 ${section.approved ? "border-emerald-300" : ""}`}
        >
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-slate-800">
              {section.section_tag.replace(/_/g, " ")}
            </span>
            <Score label="verified" pct={section.verified_pct} />
            <Score label="reqs" pct={section.requirements_covered_pct} />
            <Score label="style" pct={section.style_match_pct} />
            {section.dropped_untagged > 0 && (
              <span className="rounded bg-red-50 px-1.5 text-[11px] text-red-600">
                {section.dropped_untagged} ungrounded dropped
              </span>
            )}
            <div className="ml-auto">
              {section.approved ? (
                <span
                  data-testid="approved-badge"
                  className="rounded bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800"
                >
                  approved · {section.approved_by}
                </span>
              ) : (
                <button
                  data-testid="approve-button"
                  disabled={!canApprove(section)}
                  title={
                    section.open_flags.length
                      ? "resolve open flags first"
                      : undefined
                  }
                  onClick={() => onApprove(section.id, name.trim())}
                  className="rounded bg-indigo-600 px-2 py-0.5 text-xs font-medium text-white disabled:opacity-40"
                >
                  Approve section
                </button>
              )}
            </div>
          </div>
          {section.open_flags.length > 0 && (
            <p
              data-testid="open-flags"
              className="mb-2 text-xs font-medium text-red-600"
            >
              {section.open_flags.length} open flag(s) — resolve before approving
            </p>
          )}
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
