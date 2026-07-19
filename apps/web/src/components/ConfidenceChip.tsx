// THE confidence chip (US-13). Coloured dot + % + the "why" on hover.
// This one component is the design system's trust primitive (SPEC §17):
// every card, row, and sentence renders confidence through it.
import { bandFromConfidence, type Band } from "../confidence";

const DOT: Record<Band, string> = {
  green: "bg-emerald-500",
  yellow: "bg-amber-400",
  red: "bg-red-500",
};

const TEXT: Record<Band, string> = {
  green: "text-emerald-700",
  yellow: "text-amber-700",
  red: "text-red-700",
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
      className={`inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium ${TEXT[resolved]}`}
    >
      <span
        data-testid="chip-dot"
        className={`h-2 w-2 rounded-full ${DOT[resolved]}`}
      />
      {confidence != null ? `${Math.round(confidence * 100)}%` : "n/a"}
    </span>
  );
}
