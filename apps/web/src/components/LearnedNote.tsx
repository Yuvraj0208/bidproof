// US-20: the visible face of the correction flywheel. When past reviewer
// corrections pre-fill a clause on a new tender, the suggestion is shown with
// its provenance — learned behaviour is never silent (SPEC §8 layer 4).
import type { LearnedPrefill } from "../api";

export function LearnedNote({ learned }: { learned: LearnedPrefill }) {
  return (
    <div
      data-testid="learned-note"
      className="mt-1 rounded-[8px] border border-indigo/25 bg-indigo-tint px-2 py-1 text-[11px] text-indigo"
    >
      <span className="font-medium">🧠 Pre-filled: </span>
      <span className="font-medium text-indigo">{learned.suggested_value}</span>
      <div className="mt-0.5 text-indigo/70">
        {learned.note} · from {learned.based_on_count} past corrections · review
        before accepting
      </div>
    </div>
  );
}
