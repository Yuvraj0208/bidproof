// Proposal Studio (US-09 + US-11): the draft, section by section, with a
// per-claim badge, three per-section scores, and INDIVIDUAL approval —
// there is deliberately no "approve all" button, and a section with an open
// flag cannot be approved until it is resolved.
import { useState } from "react";
import type { Proposal, ProposalClaim, ProposalSection } from "../api";

const CLAIM_STYLE: Record<ProposalClaim["status"], string> = {
  verified: "bg-success-tint text-success",
  cannot_verify: "bg-warning-tint text-warning",
  contradicted: "bg-danger-tint text-danger",
};

const CLAIM_LABEL: Record<ProposalClaim["status"], string> = {
  verified: "verified",
  cannot_verify: "cannot verify",
  contradicted: "contradicted",
};

/** Claims still needing a decision. A resolved one keeps its badge — the
 *  record of what was wrong should not disappear once it is dealt with. */
export function isOpenFlag(claim: ProposalClaim): boolean {
  return (
    (claim.status === "contradicted" || claim.status === "cannot_verify") &&
    !claim.resolution
  );
}

/** Internal source tags belong in the provenance column, not mid-sentence. */
export function stripTags(text: string): string {
  return text.replace(/\[(?:F|P):[0-9a-f]{8}\]/g, "").replace(/\s{2,}/g, " ").trim();
}

/** The two honest answers to a flagged claim.
 *
 *  Dropping is offered first and needs nothing but a name: taking out a
 *  sentence the company cannot evidence is the safe direction. Keeping one is
 *  the decision that goes on the record, so it asks for a reason.
 */
function ClaimResolver({
  disabled,
  onResolve,
}: {
  disabled: boolean;
  onResolve: (action: "drop" | "accept", reason: string) => void;
}) {
  const [accepting, setAccepting] = useState(false);
  const [reason, setReason] = useState("");

  if (accepting) {
    return (
      <span className="mt-1 flex flex-wrap items-center gap-1">
        <input
          autoFocus
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Why is this claim right? (goes in the audit log)"
          className="min-w-[16rem] flex-1 rounded-[8px] border border-hairline px-2 py-0.5 text-[11px]"
        />
        <button
          data-testid="claim-accept-confirm"
          disabled={reason.trim().length < 10}
          onClick={() => onResolve("accept", reason.trim())}
          className="rounded-[8px] bg-indigo px-2 py-0.5 text-[11px] font-medium text-white disabled:opacity-40"
        >
          Keep it
        </button>
        <button
          onClick={() => setAccepting(false)}
          className="rounded-[8px] border border-hairline px-2 py-0.5 text-[11px] text-ink-muted"
        >
          Cancel
        </button>
      </span>
    );
  }

  return (
    <span className="mt-1 flex items-center gap-1">
      <button
        data-testid="claim-drop"
        disabled={disabled}
        title={disabled ? "enter your name above first" : undefined}
        onClick={() => onResolve("drop", "")}
        className="rounded-[8px] border border-hairline px-2 py-0.5 text-[11px] text-ink-muted hover:bg-surface disabled:opacity-40"
      >
        Remove this sentence
      </button>
      <button
        data-testid="claim-accept"
        disabled={disabled}
        title={disabled ? "enter your name above first" : undefined}
        onClick={() => setAccepting(true)}
        className="rounded-[8px] border border-hairline px-2 py-0.5 text-[11px] text-ink-muted hover:bg-surface disabled:opacity-40"
      >
        It's correct — keep it
      </button>
    </span>
  );
}

function scoreBand(pct: number | null): string {
  if (pct == null) return "bg-surface text-ink-muted";
  if (pct >= 90) return "bg-success-tint text-success";
  if (pct >= 50) return "bg-warning-tint text-warning";
  return "bg-danger-tint text-danger";
}

function Score({ label, pct }: { label: string; pct: number | null }) {
  return (
    <span
      className={`rounded-[8px] px-1.5 py-0.5 text-[11px] font-medium ${scoreBand(pct)}`}
    >
      {label} {pct == null ? "n/a" : `${pct}%`}
    </span>
  );
}

export function ProposalPanel({
  proposal,
  onGenerate,
  onApprove,
  onResolveClaim,
  busy,
}: {
  proposal: Proposal | null;
  onGenerate: () => void;
  onApprove: (sectionId: string, name: string) => void;
  onResolveClaim?: (
    sectionId: string,
    claimIndex: number,
    action: "drop" | "accept",
    by: string,
    reason: string,
  ) => void;
  busy: boolean;
}) {
  // Remembered across reloads. Approving stays one deliberate act per section
  // (SPEC §3.2 US-11: "No single 'approve all' button"), but re-typing your
  // name seven times is friction that protects nothing.
  const [name, setName] = useState(
    () => localStorage.getItem("bidproof.approver") ?? "",
  );
  const setApprover = (value: string) => {
    setName(value);
    localStorage.setItem("bidproof.approver", value);
  };
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
        <h2 className="text-sm font-semibold text-ink">Proposal draft</h2>
        {proposal && (
          <span
            data-testid="approval-progress"
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${ready ? "bg-success-tint text-success" : "bg-warning-tint text-warning"}`}
          >
            {ready
              ? "all sections approved"
              : `${approvedCount}/${proposal.sections.length} sections approved`}
          </span>
        )}
        <button
          onClick={onGenerate}
          disabled={busy}
          className="ml-auto rounded-[8px] border border-hairline px-2 py-1 text-sm text-ink-muted hover:bg-surface disabled:opacity-50"
        >
          {busy ? "Drafting…" : proposal ? "Re-draft" : "Draft proposal"}
        </button>
      </div>

      {!proposal && (
        <p className="text-sm text-ink-muted">
          No draft yet. A proposal can be drafted once the decision is GO — every
          factual sentence is grounded in your capability database.
        </p>
      )}

      {proposal && (
        <input
          value={name}
          onChange={(e) => setApprover(e.target.value)}
          placeholder="Your name (to approve sections)"
          className="w-full rounded-[8px] border border-hairline px-2 py-1 text-sm"
        />
      )}

      {proposal?.sections.map((section) => (
        <article
          key={section.id}
          data-testid="proposal-section"
          className={`rounded-[12px] border bg-white p-4 ${section.approved ? "border-success/40" : "border-hairline"}`}
        >
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-ink">
              {section.section_tag.replace(/_/g, " ")}
            </span>
            <Score label="verified" pct={section.verified_pct} />
            <Score label="reqs" pct={section.requirements_covered_pct} />
            <Score label="style" pct={section.style_match_pct} />
            {section.dropped_untagged > 0 && (
              <span className="rounded-[8px] bg-danger-tint px-1.5 text-[11px] text-danger">
                {section.dropped_untagged} ungrounded dropped
              </span>
            )}
            <div className="ml-auto">
              {section.approved ? (
                <span
                  data-testid="approved-badge"
                  className="rounded-[8px] bg-success-tint px-2 py-0.5 text-xs font-medium text-success"
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
                  className="rounded-[8px] bg-indigo px-2 py-0.5 text-xs font-medium text-white disabled:opacity-40"
                >
                  Approve section
                </button>
              )}
            </div>
          </div>
          {section.open_flags.length > 0 && (
            <p
              data-testid="open-flags"
              className="mb-2 text-xs font-medium text-danger"
            >
              {section.open_flags.length} open flag(s) — resolve below, then
              approve
            </p>
          )}
          {/* The reader-facing prose. The tagged original stays in
              `section.content`, and the claims below carry the provenance. */}
          <pre
            data-testid="section-prose"
            className="whitespace-pre-wrap rounded-[8px] bg-surface p-3 text-xs text-ink"
          >
            {section.content_display ?? section.content}
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
                    className={`shrink-0 rounded-[8px] px-1.5 ${CLAIM_STYLE[claim.status]}`}
                  >
                    {CLAIM_LABEL[claim.status]}
                  </span>
                  <span className="text-ink-muted">
                    {stripTags(claim.text)}
                    {claim.source_tag && (
                      <span className="ml-1 font-mono text-ink-subtle">
                        {claim.source_tag}
                      </span>
                    )}
                    {claim.resolution && (
                      <span
                        data-testid="claim-resolved"
                        className="ml-1 text-success"
                      >
                        · {claim.resolution === "drop"
                          ? "sentence removed"
                          : "accepted"} by {claim.resolved_by}
                      </span>
                    )}
                    {isOpenFlag(claim) && onResolveClaim && (
                      <ClaimResolver
                        disabled={name.trim().length < 2}
                        onResolve={(action, reason) =>
                          onResolveClaim(section.id, i, action, name.trim(), reason)
                        }
                      />
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
