// Evaluation (SPEC §14/§19): what each part of the pipeline actually scores,
// measured on demand against real ground truth.
//
// The screen's job is to make a number's PROVENANCE as visible as the number.
// A precision of 1.00 against synthetic fixtures and 1.00 against hand-labelled
// tenders are different claims, and showing them identically would be the
// dishonesty this whole subsystem exists to prevent. So every card carries its
// ground-truth kind, its sample size, and — when it cannot be measured — what
// would have to be true for it to be.
import { Stagger } from "../ui/motion";
import { useEffect, useState } from "react";
import {
  fetchEvaluationCatalogue,
  runEvaluation,
  type EvaluationResult,
  type EvaluationMetric,
} from "../api";
import { MetricBar } from "../ui/charts";
import { Button, Card, EmptyState, FieldLabel, SkeletonLoader } from "../ui/primitives";
import { Pill } from "../ui/chips";
import { useToast } from "../ui/overlays";

type PillTone = "neutral" | "brand" | "warning";

const GROUND_TRUTH_COPY: Record<string, { label: string; tone: PillTone; why: string }> = {
  human_labelled: {
    label: "hand-labelled",
    tone: "brand",
    why: "A person wrote down the right answer for a real document. The strongest evidence available.",
  },
  synthetic: {
    label: "synthetic",
    tone: "warning",
    why: "We generated the documents, so the answer is known exactly — but it only tests what we generated.",
  },
  derived: {
    label: "derived",
    tone: "neutral",
    why: "No labels: two implementations compared, or a property that must hold whatever the answer is.",
  },
  self_reported: {
    label: "self-reported",
    tone: "warning",
    why: "Scored by a checker that is part of the product, so it is real data but not an independent judge.",
  },
  none: { label: "no ground truth", tone: "warning", why: "Nothing to measure against yet." },
};

function MetricRow({ metric }: { metric: EvaluationMetric }) {
  const pct = metric.unit === "ratio" && metric.value !== null;
  const shown =
    metric.value === null
      ? "—"
      : pct
        ? `${(metric.value * 100).toFixed(1)}%`
        : `${metric.value}${metric.unit && metric.unit !== "count" ? ` ${metric.unit}` : ""}`;

  return (
    <div
      data-testid="eval-metric"
      className="flex items-baseline justify-between gap-3 border-b border-hairline py-1.5 last:border-0"
    >
      <div className="min-w-0">
        <div className="text-sm text-ink">{metric.label}</div>
        {metric.detail && (
          <div className="text-[11px] text-ink-subtle">{metric.detail}</div>
        )}
      </div>
      <div className="w-32 shrink-0 text-right">
        <span data-numeric className="text-sm font-semibold text-ink">
          {shown}
        </span>
        {/* A ratio gets a bar as well as a figure: the number is the claim, the
            bar is how far from 1.0 it sits. Counts and durations get no bar,
            because there is nothing to be a fraction OF. */}
        {pct && (
          <div className="mt-1">
            <MetricBar
              value={metric.value}
              higherIsBetter={metric.higher_is_better}
              label={metric.label}
            />
          </div>
        )}
        <div className="mt-1 text-[11px] text-ink-subtle">
          {metric.sample_size !== null ? `n=${metric.sample_size}` : ""}
          {!metric.higher_is_better && metric.value !== null ? " · lower is better" : ""}
        </div>
      </div>
    </div>
  );
}

function ResultCard({ result }: { result: EvaluationResult }) {
  const truth = GROUND_TRUTH_COPY[result.ground_truth] ?? GROUND_TRUTH_COPY.none;
  const measured = result.status === "measured";

  return (
    <Card data-testid="eval-card" className="mb-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-ink">{result.label}</div>
          <p className="mt-0.5 max-w-2xl text-xs text-ink-muted">
            {result.what_it_measures}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          {measured ? (
            <span title={truth.why}>
              <Pill tone={truth.tone}>{truth.label}</Pill>
            </span>
          ) : (
            <Pill tone="warning">{result.status.replace(/_/g, " ")}</Pill>
          )}
          {result.duration_s !== null && (
            <span className="text-[11px] text-ink-subtle">{result.duration_s}s</span>
          )}
        </div>
      </div>

      {measured && result.metrics.length > 0 && (
        <div className="mt-3">
          {result.metrics.map((m) => (
            <MetricRow key={m.key} metric={m} />
          ))}
        </div>
      )}

      {/* The caveat is not a footnote: a synthetic 100% that reads like a real
          100% is exactly the failure this screen exists to prevent. */}
      {result.blocked_reason && (
        <div
          data-testid="eval-caveat"
          className="mt-3 rounded-[8px] bg-surface px-3 py-2 text-xs text-ink-muted"
        >
          <span className="font-medium text-ink">
            {measured ? "Read this before trusting the number: " : "Not measured: "}
          </span>
          {result.blocked_reason}
          {result.how_to_fix && (
            <div className="mt-1">
              <span className="font-medium text-ink">To fix: </span>
              {result.how_to_fix}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

export default function Evaluation() {
  const { push } = useToast();
  const [results, setResults] = useState<EvaluationResult[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [known, setKnown] = useState<{ component: string; cost: string }[]>([]);

  useEffect(() => {
    fetchEvaluationCatalogue()
      .then((c) => setKnown(c.components))
      .catch(() => setKnown([]));
  }, []);

  const run = async (includeSlow: boolean) => {
    setBusy(includeSlow ? "Measuring everything…" : "Measuring…");
    try {
      const out = await runEvaluation({ includeSlow });
      setResults(out.results);
      const measured = out.results.filter((r) => r.status === "measured").length;
      push(`${measured} of ${out.results.length} components measured.`, "success");
    } catch (e) {
      push(`Evaluation failed: ${String(e)}`, "danger");
    } finally {
      setBusy(null);
    }
  };

  const slowCount = known.filter((k) => k.cost === "slow").length;

  return (
    <div className="p-6">
      <header className="mb-4">
        <h1 className="text-lg font-semibold text-ink">Evaluation</h1>
        <p className="mt-1 max-w-3xl text-sm text-ink-muted">
          What each part of the pipeline actually scores, measured on demand
          against real ground truth. Nothing here is a default or an estimate —
          a component with nothing to measure against says so, and says what it
          would need.
        </p>
      </header>

      <div className="mb-5 flex flex-wrap items-center gap-2">
        <Button variant="primary" disabled={busy !== null} onClick={() => run(false)}>
          {busy ?? "Run the fast checks"}
        </Button>
        <Button disabled={busy !== null} onClick={() => run(true)}>
          Run everything (loads models, minutes)
        </Button>
        {slowCount > 0 && (
          <span className="text-xs text-ink-subtle">
            {slowCount} slow {slowCount === 1 ? "check" : "checks"}: OCR and the
            text-engine comparison read real PDFs.
          </span>
        )}
      </div>

      {busy && (
        <Card>
          <SkeletonLoader rows={4} />
        </Card>
      )}

      {!busy && results === null && (
        <EmptyState
          title="Nothing measured in this session yet"
          body="Run the checks to score extraction, scraping, proposals, OCR and the text engines against their ground truth."
          action={
            <Button variant="primary" onClick={() => run(false)}>
              Run the fast checks
            </Button>
          }
        />
      )}

      {!busy && results !== null && (
        <>
          <FieldLabel>Results</FieldLabel>
          <Stagger className="mt-2">
            {results.map((r) => (
              <ResultCard key={r.component} result={r} />
            ))}
          </Stagger>
        </>
      )}
    </div>
  );
}
