// The Compliance Matrix (US-05) — the money table. Every row: rule ×
// our position, verdict, confidence chip, and click-to-proof.
import { ConfidenceChip } from "./ConfidenceChip";
import type { Highlight } from "./PdfProof";

export interface VerdictRow {
  id: string;
  family: string;
  key: string;
  requirement_text: string;
  value: string | null;
  verdict: string;
  reason: string;
  confidence: number;
  band: "green" | "yellow" | "red";
  arithmetic: boolean;
  page_no: number;
  bbox: { x0: number; y0: number; x1: number; y1: number };
}

const VERDICT_STYLE: Record<string, string> = {
  complies: "bg-emerald-100 text-emerald-800",
  partial: "bg-amber-100 text-amber-800",
  gap: "bg-red-100 text-red-800",
  not_applicable: "bg-slate-100 text-slate-600",
  needs_human: "bg-red-100 text-red-800",
};

export function MatrixTable({
  verdicts,
  onProof,
}: {
  verdicts: VerdictRow[];
  onProof: (highlight: Highlight) => void;
}) {
  if (verdicts.length === 0) {
    return (
      <p className="p-4 text-sm text-slate-500">
        No verdicts yet — run the check first.
      </p>
    );
  }
  return (
    <table className="w-full text-left text-sm">
      <thead className="sticky top-0 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
        <tr>
          <th className="px-3 py-2">Rule</th>
          <th className="px-3 py-2">Our position</th>
          <th className="px-3 py-2">Verdict</th>
          <th className="px-3 py-2">Confidence</th>
        </tr>
      </thead>
      <tbody>
        {verdicts.map((row) => (
          <tr
            key={row.id}
            data-testid="matrix-row"
            onClick={() => onProof({ page_no: row.page_no, bbox: row.bbox })}
            className="cursor-pointer border-b align-top hover:bg-amber-50"
          >
            <td className="px-3 py-2">
              <div className="font-mono text-xs text-slate-700">{row.key}</div>
              <div className="mt-0.5 line-clamp-2 text-xs text-slate-500">
                {row.requirement_text}
              </div>
              <div className="mt-0.5 text-[11px] text-slate-400">
                {row.family} · p.{row.page_no} · proof ↗
              </div>
            </td>
            <td className="px-3 py-2 text-xs text-slate-600">{row.reason}</td>
            <td className="px-3 py-2">
              <span
                className={`rounded px-2 py-0.5 text-xs font-medium ${VERDICT_STYLE[row.verdict] ?? ""}`}
              >
                {row.verdict.replace("_", " ")}
              </span>
              {row.verdict === "needs_human" && (
                <div
                  data-testid="queued-badge"
                  className="mt-1 text-[11px] font-medium text-red-600"
                >
                  queued for human
                </div>
              )}
            </td>
            <td className="px-3 py-2">
              <ConfidenceChip
                confidence={row.confidence}
                band={row.band}
                reason={row.reason}
              />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
