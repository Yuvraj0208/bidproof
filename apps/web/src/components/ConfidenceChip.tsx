// THE confidence chip (US-13). Coloured dot + % + the "why" on hover.
// This one component is the design system's trust primitive (SPEC §17):
// every card, row, and sentence renders confidence through it.
import { bandFromConfidence, type Band } from "../confidence";

// Restyled onto the design tokens (Task 4) — the API is unchanged on purpose:
// this chip is the trust primitive and appears on every card, row and sentence.
//
// The DOT classes stay on the literal Tailwind palette because
// ConfidenceChip.test.tsx asserts these exact class names, and the Task-4 brief
// requires the retrofit to leave existing tests untouched. The surrounding
// chip (border/background/text) is fully tokenised; only the 8px dot differs.
const DOT: Record<Band, string> = {
  green: "bg-emerald-500",
  yellow: "bg-amber-400",
  red: "bg-red-500",
};

const TEXT: Record<Band, string> = {
  green: "border-success/25 bg-success-tint text-success",
  yellow: "border-warning/25 bg-warning-tint text-warning",
  red: "border-danger/25 bg-danger-tint text-danger",
};

export interface ConfidenceChipProps {
  confidence: number | null;
  band?: Band | null;
  reason?: string | null;
}

export function ConfidenceChip({ confidence, band, reason }: ConfidenceChipProps) {
  const resolved: Band =
    band ?? (confidence != null ? bandFromConfidence(confidence) : "red");
  return (
    <span
      data-band={resolved}
      title={reason ?? undefined}
      className={`inline-flex items-center gap-1.5 rounded-[8px] border px-2 py-0.5 text-xs font-medium ${TEXT[resolved]}`}
    >
      <span
        data-testid="chip-dot"
        className={`h-2 w-2 rounded-full ${DOT[resolved]}`}
      />
      {confidence != null ? `${Math.round(confidence * 100)}%` : "n/a"}
    </span>
  );
}
