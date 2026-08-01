// Status primitives. Every one of these carries a GLYPH or a WORD as well as a
// colour — a bid manager may be colour-blind, and a projector may wash the hues
// out entirely. Colour is the accent, never the message (SPEC §17).
import { Clock } from "lucide-react";
import type { ReactNode } from "react";

/** VerdictBadge — the compliance matrix's verdict cell. */
// The label is always the API's own verdict word (underscores softened to
// spaces) rather than a prettier synonym: the screen, the exported .xlsx and
// the audit log must all say the same thing, so a reviewer can match them.
const VERDICTS: Record<string, { glyph: string; className: string }> = {
  complies: { glyph: "✓", className: "bg-success-tint text-success border-success/25" },
  partial: { glyph: "◐", className: "bg-warning-tint text-warning border-warning/25" },
  gap: { glyph: "✕", className: "bg-danger-tint text-danger border-danger/25" },
  needs_human: { glyph: "?", className: "bg-danger-tint text-danger border-danger/25" },
  not_applicable: {
    glyph: "–",
    className: "bg-indigo-tint text-ink-muted border-hairline",
  },
};

export function VerdictBadge({ verdict }: { verdict: string }) {
  const style = VERDICTS[verdict] ?? {
    glyph: "•",
    className: "bg-indigo-tint text-ink-muted border-hairline",
  };
  const v = { ...style, label: verdict.replace(/_/g, " ") };
  return (
    <span
      data-testid="verdict-badge"
      className={`inline-flex items-center gap-1.5 rounded-[8px] border px-2 py-0.5 text-xs font-medium ${v.className}`}
    >
      <span aria-hidden className="font-semibold">{v.glyph}</span>
      {v.label}
    </span>
  );
}

/** Days between now and an ISO timestamp. Exported for the countdown tests —
 *  deadline arithmetic is the thing you least want to get wrong. */
export function daysUntil(iso: string | null, now: Date = new Date()): number | null {
  if (!iso) return null;
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return null;
  return (then - now.getTime()) / 86_400_000;
}

/** CountdownChip — amber under 7 days, red under 3, pulsing under 24 hours.
 *  A closed tender is stated plainly rather than shown as a negative number. */
export function CountdownChip({
  closingAt,
  now,
}: {
  closingAt: string | null;
  now?: Date;
}) {
  const days = daysUntil(closingAt, now);
  if (days === null) {
    return (
      <span
        data-testid="countdown-chip"
        className="inline-flex items-center gap-1 rounded-[8px] border border-hairline bg-white px-2 py-0.5 text-xs text-ink-subtle"
      >
        No deadline
      </span>
    );
  }

  let tone = "border-hairline bg-white text-ink-muted";
  let urgent = false;
  let label: string;

  if (days < 0) {
    tone = "border-hairline bg-indigo-tint text-ink-subtle";
    label = "Closed";
  } else {
    const hours = days * 24;
    if (hours < 24) {
      tone = "border-danger/25 bg-danger-tint text-danger";
      urgent = true;
      label = hours < 1 ? "Closing now" : `${Math.floor(hours)}h left`;
    } else if (days < 3) {
      tone = "border-danger/25 bg-danger-tint text-danger";
      label = `${Math.floor(days)}d left`;
    } else if (days < 7) {
      tone = "border-warning/25 bg-warning-tint text-warning";
      label = `${Math.floor(days)}d left`;
    } else {
      label = `${Math.floor(days)}d left`;
    }
  }

  return (
    <span
      data-testid="countdown-chip"
      data-urgent={urgent ? "true" : undefined}
      data-numeric
      className={`inline-flex items-center gap-1 rounded-[8px] border px-2 py-0.5 text-xs font-medium ${tone} ${
        urgent ? "animate-urgent" : ""
      }`}
    >
      <Clock size={12} strokeWidth={2} aria-hidden className="shrink-0" />
      {label}
    </span>
  );
}

/** Format rupees the way Indian finance reads them: lakh and crore, not
 *  millions. Exported because the Decision Room and the matrix must agree. */
export function formatInr(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const abs = Math.abs(value);
  const sign = value < 0 ? "−" : "";
  if (abs >= 1e7) return `${sign}₹${(abs / 1e7).toFixed(2)} crore`;
  if (abs >= 1e5) return `${sign}₹${(abs / 1e5).toFixed(2)} lakh`;
  return `${sign}₹${Math.round(abs).toLocaleString("en-IN")}`;
}

/** RiskTag — a risk is only real when it carries its rupee impact. */
export function RiskTag({
  label,
  impactInr,
  severity = "medium",
}: {
  label: string;
  impactInr?: number | null;
  severity?: "low" | "medium" | "high";
}) {
  const tones: Record<string, string> = {
    low: "border-hairline bg-indigo-tint text-ink-muted",
    medium: "border-warning/25 bg-warning-tint text-warning",
    high: "border-danger/25 bg-danger-tint text-danger",
  };
  return (
    <span
      data-testid="risk-tag"
      className={`inline-flex items-center gap-1.5 rounded-[8px] border px-2 py-0.5 text-xs font-medium ${tones[severity]}`}
    >
      <span aria-hidden>⚠</span>
      <span>{label}</span>
      {impactInr != null && (
        <span data-numeric className="font-semibold">
          {formatInr(impactInr)}
        </span>
      )}
    </span>
  );
}

/** Small neutral pill used for source/provenance chips. */
export function Pill({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "brand" | "warning";
}) {
  const tones: Record<string, string> = {
    neutral: "border-hairline bg-white text-ink-muted",
    brand: "border-indigo/20 bg-indigo-tint text-indigo",
    warning: "border-warning/25 bg-warning-tint text-warning",
  };
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-[8px] border px-2 py-0.5 text-xs ${tones[tone]}`}
    >
      {children}
    </span>
  );
}
