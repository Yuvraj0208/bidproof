// The Compliance Matrix (US-05) — the money table.
//
// Every row: the rule, our position, the verdict, its confidence, and the page
// it came from. Clicking anywhere on the row drives click-to-proof. Built on
// the shared DataTable so it inherits the sticky header, sorting, zebra rows,
// keyboard navigation and the density toggle (SPEC §17).
import { useMemo, useState } from "react";
import { ConfidenceChip } from "./ConfidenceChip";
import type { Highlight } from "./PdfProof";
import { DataTable, type Column } from "../ui/DataTable";
import { VerdictBadge } from "../ui/chips";
import { Button, EmptyState } from "../ui/primitives";

export interface VerdictRow {
  id: string;
  rule_id: string;
  family: string;
  key: string;
  requirement_text: string;
  value: string | null;
  verdict: string;
  reason: string;
  confidence: number;
  band: "green" | "yellow" | "red";
  arithmetic: boolean;
  document_id: string;
  page_no: number;
  bbox: { x0: number; y0: number; x1: number; y1: number };
  // Present once a human has settled this one (SPEC §7 checkpoint 3).
  system_verdict: string | null;
  decided_by: string | null;
  decided_at: string | null;
  decided_reason: string | null;
}

// The order a bid manager triages in: what blocks us, then what needs us.
const VERDICT_ORDER: Record<string, number> = {
  gap: 0,
  needs_human: 1,
  partial: 2,
  complies: 3,
  not_applicable: 4,
};

export function MatrixTable({
  verdicts,
  onProof,
  onDecide,
}: {
  verdicts: VerdictRow[];
  onProof: (highlight: Highlight) => void;
  /** Open the decision form for a verdict the system would not guess. */
  onDecide?: (row: VerdictRow) => void;
}) {
  const [filter, setFilter] = useState<string>("all");

  const families = useMemo(
    () => Array.from(new Set(verdicts.map((v) => v.family))).sort(),
    [verdicts],
  );

  const rows = useMemo(() => {
    if (filter === "all") return verdicts;
    if (filter === "attention")
      return verdicts.filter((v) => ["gap", "needs_human", "partial"].includes(v.verdict));
    return verdicts.filter((v) => v.family === filter);
  }, [verdicts, filter]);

  const columns: Column<VerdictRow>[] = [
    {
      key: "rule",
      header: "Rule",
      width: "42%",
      sortValue: (row) => row.key,
      render: (row) => (
        <div className="min-w-0">
          <div className="font-mono text-xs text-ink-muted">{row.key}</div>
          <div className="mt-0.5 line-clamp-2 text-sm text-ink">
            {row.requirement_text}
          </div>
          <div className="mt-1 text-[11px] text-ink-subtle">
            {row.family} · p.{row.page_no} · proof ↗
          </div>
        </div>
      ),
    },
    {
      key: "position",
      header: "Our position",
      width: "30%",
      render: (row) => (
        <span className="text-sm text-ink-muted">{row.reason}</span>
      ),
    },
    {
      key: "verdict",
      header: "Verdict",
      sortValue: (row) => VERDICT_ORDER[row.verdict] ?? 9,
      render: (row) => (
        <div className="flex flex-col items-start gap-1">
          <VerdictBadge verdict={row.verdict} />
          {row.verdict === "needs_human" && (
            <>
              <span
                data-testid="queued-badge"
                className="text-[11px] font-medium text-danger"
              >
                queued for human
              </span>
              {onDecide && (
                <button
                  data-testid="decide-verdict"
                  onClick={(event) => {
                    // The row itself opens the proof; this must not do both.
                    event.stopPropagation();
                    onDecide(row);
                  }}
                  className="rounded-[8px] border border-indigo/25 bg-indigo-tint px-2 py-0.5 text-[11px] font-medium text-indigo transition-colors duration-150 hover:bg-indigo/10"
                >
                  Decide →
                </button>
              )}
            </>
          )}
          {row.decided_by && (
            /* A human answer is never dressed up as a machine one. */
            <span
              data-testid="decided-badge"
              className="text-[11px] text-ink-subtle"
            >
              you decided · was {row.system_verdict ?? "unknown"}
            </span>
          )}
          {row.arithmetic && (
            <span className="text-[11px] text-ink-subtle">checked by code</span>
          )}
        </div>
      ),
    },
    {
      key: "confidence",
      header: "Confidence",
      align: "right",
      numeric: true,
      sortValue: (row) => row.confidence,
      render: (row) => (
        <ConfidenceChip
          confidence={row.confidence}
          band={row.band}
          reason={row.reason}
        />
      ),
    },
  ];

  const needsAttention = verdicts.filter((v) =>
    ["gap", "needs_human", "partial"].includes(v.verdict),
  ).length;

  return (
    <div className="p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Button
          size="sm"
          variant={filter === "all" ? "primary" : "secondary"}
          onClick={() => setFilter("all")}
        >
          All {verdicts.length}
        </Button>
        <Button
          size="sm"
          variant={filter === "attention" ? "primary" : "secondary"}
          onClick={() => setFilter("attention")}
        >
          Needs attention {needsAttention}
        </Button>
        {families.map((family) => (
          <Button
            key={family}
            size="sm"
            variant={filter === family ? "primary" : "secondary"}
            onClick={() => setFilter(family)}
          >
            {family}
          </Button>
        ))}
      </div>

      <DataTable<VerdictRow>
        rows={rows}
        rowKey={(row) => row.id}
        rowTestId="matrix-row"
        caption={`${rows.length} of ${verdicts.length} requirements`}
        onRowActivate={(row) =>
          onProof({
            page_no: row.page_no,
            bbox: row.bbox,
            document_id: row.document_id,
          })
        }
        columns={columns}
        empty={
          <EmptyState
            title="No verdicts yet"
            body="Run the check to compare every extracted rule against your capability database. Each verdict will click back to its page."
          />
        }
      />
    </div>
  );
}
