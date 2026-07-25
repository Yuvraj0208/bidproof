// Review — every human decision for this tender, in one place (FINISH_STATUS R3).
//
// The checkpoints of SPEC §7 were spread across seven different tabs, so there
// was no way to answer "what is waiting for me?". This screen collects them,
// numbered as the SPEC numbers them, each with the reason it is waiting and a
// link straight to the control that clears it. It reads state the Workspace has
// already fetched — it adds no requests and owns no truth of its own.
import type { ReactNode } from "react";
import { Pill } from "../ui/chips";
import { Button, Card, EmptyState, FieldLabel } from "../ui/primitives";

export interface ReviewItem {
  checkpoint: number;
  title: string;
  detail: string;
  count: number;
  /** Which workspace tab clears it. */
  goTo: string;
  action: string;
  blocking: boolean;
}

/** Derive the outstanding human actions. Pure — trivial to test and to reason
 *  about, and it cannot disagree with the tabs because it reads their data. */
export function pendingReviews(input: {
  radarList?: string | null;
  checkpoint0?: string | null;
  rulesNeedingHuman: number;
  verdictsNeedingHuman: number;
  decisionStatus?: string | null;
  decisionRecommendation?: string | null;
  proposalSections?: { approved: boolean }[] | null;
  exportBlockers?: number | null;
  checklistRequired?: number | null;
  checklistTicked?: number | null;
}): ReviewItem[] {
  const items: ReviewItem[] = [];

  if (input.checkpoint0 === "queued" || input.radarList === "needs_human") {
    items.push({
      checkpoint: 0,
      title: "Confirm this tender belongs in your lane",
      detail:
        "Triage could not decide with confidence, so it is parked for a human. Accept it into a lane or drop it.",
      count: 1,
      goTo: "rules",
      action: "Review triage",
      blocking: false,
    });
  }

  if (input.rulesNeedingHuman > 0) {
    items.push({
      checkpoint: 2,
      title: "Accept or correct extracted rules",
      detail:
        "These clauses were read with low confidence. Each one clicks through to its page and box so you can check the source.",
      count: input.rulesNeedingHuman,
      goTo: "rules",
      action: "Open rules",
      blocking: false,
    });
  }

  if (input.verdictsNeedingHuman > 0) {
    items.push({
      checkpoint: 3,
      title: "Decide the verdicts the system would not guess",
      detail:
        "No arithmetic and no cited judgement could settle these, so they are yours. The system says 'I do not know' rather than guessing.",
      count: input.verdictsNeedingHuman,
      goTo: "matrix",
      action: "Open matrix",
      blocking: true,
    });
  }

  if (input.decisionStatus === "pending_signoff") {
    items.push({
      checkpoint: 4,
      title: `Sign off the ${(input.decisionRecommendation ?? "bid").toUpperCase()} decision`,
      detail:
        "The expected value is computed, term by term, but the call is a named human's. Bid Head role required — you can also override with a written reason.",
      count: 1,
      goTo: "decision",
      action: "Open decision room",
      blocking: true,
    });
  }

  const sections = input.proposalSections ?? [];
  const unapproved = sections.filter((s) => !s.approved).length;
  if (unapproved > 0) {
    items.push({
      checkpoint: 5,
      title: "Approve proposal sections",
      detail:
        "Every factual sentence is tagged to your own data and fact-checked, but no section leaves without a human approving it.",
      count: unapproved,
      goTo: "proposal",
      action: "Open proposal",
      blocking: true,
    });
  }

  if ((input.exportBlockers ?? 0) > 0) {
    items.push({
      checkpoint: 6,
      title: "Clear the export blockers",
      detail:
        "Export is refused while a mandatory clause is unaddressed or a claim is contradicted. Fix them, or override with a name and a written reason.",
      count: input.exportBlockers ?? 0,
      goTo: "proposal",
      action: "Review blockers",
      blocking: true,
    });
  }

  const required = input.checklistRequired ?? 0;
  const ticked = input.checklistTicked ?? 0;
  if (required > 0 && ticked < required) {
    items.push({
      checkpoint: 6,
      title: "Tick off the submission checklist",
      detail:
        "Each document is checked for format and signature, then a named human confirms it. Submission stays blocked until all are ticked.",
      count: required - ticked,
      goTo: "checklist",
      action: "Open checklist",
      blocking: true,
    });
  }

  return items.sort((a, b) => a.checkpoint - b.checkpoint);
}

export function ReviewHub({
  items,
  onGoTo,
  header,
}: {
  items: ReviewItem[];
  onGoTo: (tab: string) => void;
  header?: ReactNode;
}) {
  const blocking = items.filter((i) => i.blocking).length;

  return (
    <div className="mx-auto max-w-3xl p-6">
      {header}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <FieldLabel>Waiting for you</FieldLabel>
        {items.length > 0 && (
          <>
            <Pill tone="brand">{items.length} action(s)</Pill>
            {blocking > 0 && <Pill tone="warning">{blocking} blocking submission</Pill>}
          </>
        )}
      </div>

      {items.length === 0 ? (
        <EmptyState
          icon="✓"
          title="Nothing is waiting for you"
          body="Every checkpoint on this tender is clear. When the system is unsure, or when a decision is a human's to make, it will appear here."
        />
      ) : (
        <ul className="space-y-3">
          {items.map((item) => (
            <li key={`${item.checkpoint}-${item.title}`}>
              <Card className={item.blocking ? "border-warning/30" : ""}>
                <div data-testid="review-item" className="flex items-start gap-3">
                  <span
                    aria-hidden
                    className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-indigo text-xs font-semibold text-white"
                    title={`Checkpoint ${item.checkpoint}`}
                  >
                    {item.checkpoint}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-semibold text-ink">
                        {item.title}
                      </span>
                      <span
                        data-numeric
                        className="rounded-[8px] bg-surface px-1.5 text-xs font-medium text-ink-muted"
                      >
                        {item.count}
                      </span>
                      {item.blocking && <Pill tone="warning">blocks submission</Pill>}
                    </div>
                    <p className="mt-1 text-sm text-ink-muted">{item.detail}</p>
                  </div>
                  <Button
                    size="sm"
                    variant={item.blocking ? "primary" : "secondary"}
                    onClick={() => onGoTo(item.goTo)}
                  >
                    {item.action} →
                  </Button>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
