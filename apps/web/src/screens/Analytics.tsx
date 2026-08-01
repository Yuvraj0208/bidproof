// Analytics (SPEC §17 screen 8).
//
// Reads the same tables the pipeline writes, so a number here can never
// disagree with a number in the pilot report. Where a metric is not yet
// calibrated the screen SAYS SO (is_this_honest: false) instead of drawing a
// confident-looking curve over data we do not have.
import { Reveal } from "../ui/motion";
import { useEffect, useState } from "react";
import { API_BASE, authHeaders } from "../api";
import { formatInr } from "../ui/chips";
import { BarSeries, Donut, Funnel } from "../ui/charts";
import {
  Card,
  FieldLabel,
  PageHeader,
  SkeletonLoader,
  StatCallout,
} from "../ui/primitives";

interface Kpi {
  key: string;
  label: string;
  value: number | null;
  target: number | null;
  unit: string;
  meets: boolean | null;
  is_this_honest: boolean;
  note: string | null;
}

interface Overview {
  window_days: number;
  funnel: { stage: string; count: number }[];
  tat_minutes: { median: number | null; samples: number; is_this_honest: boolean };
  dq_risks: { total: number; by_family: { family: string; count: number }[]; is_this_honest: boolean };
  cost: {
    total_inr: number;
    per_tender_inr: number | null;
    trend: { day: string; cost_inr: number; calls: number; tokens: number }[];
    is_this_honest: boolean;
  };
  confidence_bands: Record<string, number>;
  calibration: { points: unknown[]; is_this_honest: boolean; note: string };
  coverage_accuracy: { points: unknown[]; is_this_honest: boolean; note: string };
  kpis: Kpi[];
}

/** The honesty marker the SPEC asks for — never a fake number. */
function NotCalibrated({ note }: { note: string }) {
  return (
    <div
      data-testid="not-honest"
      className="rounded-[8px] border border-dashed border-warning/40 bg-warning-tint px-3 py-2 text-xs text-warning"
    >
      <span className="font-medium">Not calibrated yet — </span>
      {note}
    </div>
  );
}

export default function Analytics() {
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/analytics/overview`, { headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then(setData)
      .catch((e) => setError(String(e)));
  }, []);

  if (error) {
    return (
      <div className="mx-auto max-w-5xl px-6 py-8">
        <PageHeader title="Analytics" />
        <Card className="border-danger/25 bg-danger-tint">
          <div className="text-sm font-medium text-danger">Could not load analytics</div>
          <div className="mt-1 text-xs text-danger/80">{error}</div>
        </Card>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="mx-auto max-w-5xl px-6 py-8">
        <PageHeader title="Analytics" subtitle="Loading the pipeline's own numbers…" />
        <div className="grid gap-4 md:grid-cols-2">
          <Card><SkeletonLoader rows={5} /></Card>
          <Card><SkeletonLoader rows={5} /></Card>
        </div>
      </div>
    );
  }

  const maxCost = Math.max(...data.cost.trend.map((t) => t.cost_inr), 0.0001);

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <PageHeader
        title="Analytics"
        subtitle={`Pipeline health over the last ${data.window_days} days, read from the live tables.`}
      />

      {/* KPI panel vs the SPEC §19 targets */}
      <Card className="mb-4">
        <FieldLabel>KPIs vs targets</FieldLabel>
        <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.kpis.map((kpi) => (
            <div key={kpi.key} data-testid="kpi">
              <StatCallout
                label={kpi.label}
                value={
                  kpi.is_this_honest && kpi.value !== null
                    ? kpi.key === "cost_per_tender_inr"
                      ? formatInr(kpi.value)
                      : `${kpi.value}${kpi.unit}`
                    : "—"
                }
                hint={
                  kpi.target !== null
                    ? `target ${kpi.key === "cost_per_tender_inr" ? "<₹" : "<"}${kpi.target}${kpi.unit && kpi.key !== "cost_per_tender_inr" ? kpi.unit : ""}`
                    : (kpi.note ?? undefined)
                }
                tone={kpi.meets === true ? "success" : kpi.meets === false ? "danger" : "neutral"}
              />
              {!kpi.is_this_honest && (
                <div className="mt-2">
                  <NotCalibrated note={kpi.note ?? "not measured yet"} />
                </div>
              )}
            </div>
          ))}
        </div>
      </Card>

      <Reveal className="mb-4 grid gap-4 md:grid-cols-2">
        <Card>
          <FieldLabel>Pipeline funnel</FieldLabel>
          <p className="mt-1 text-xs text-ink-subtle">
            How many tenders survive each stage. The drop between two stages is
            the number worth reading.
          </p>
          <div className="mt-3">
            <Funnel stages={data.funnel} />
          </div>
        </Card>

        <Card>
          <FieldLabel>Disqualification risks caught</FieldLabel>
          <div className="mt-3">
            <StatCallout
              label="Before submission"
              value={data.dq_risks.total}
              hint="gaps and needs-human verdicts raised by the matrix"
              tone={data.dq_risks.total > 0 ? "warning" : "neutral"}
              size="lg"
            />
            {data.dq_risks.by_family.length > 0 ? (
              <div className="mt-4">
                <BarSeries
                  fill="fill-warning"
                  data={data.dq_risks.by_family.map((f) => ({
                    label: f.family,
                    value: f.count,
                  }))}
                />
              </div>
            ) : (
              <p className="mt-3 text-sm text-ink-muted">
                No blocking findings yet — run a compliance check.
              </p>
            )}
          </div>
        </Card>
      </Reveal>

      <Reveal className="mb-4 grid gap-4 md:grid-cols-2">
        <Card>
          <FieldLabel>Turnaround time</FieldLabel>
          <div className="mt-3">
            {data.tat_minutes.is_this_honest ? (
              <StatCallout
                label="Upload → decision (median)"
                value={`${data.tat_minutes.median} min`}
                hint={`${data.tat_minutes.samples} tender(s) · target under 10 min`}
                tone={(data.tat_minutes.median ?? 99) < 10 ? "success" : "warning"}
                size="lg"
              />
            ) : (
              <NotCalibrated note="no tender has reached a decision yet" />
            )}
          </div>
        </Card>

        <Card>
          <FieldLabel>Cost trend</FieldLabel>
          <div className="mt-3">
            <StatCallout
              label="Spend in window"
              value={formatInr(data.cost.total_inr)}
              hint={
                data.cost.per_tender_inr !== null
                  ? `${formatInr(data.cost.per_tender_inr)} per decided tender`
                  : "no decided tender yet"
              }
              tone="brand"
              trend={data.cost.trend.map((d) => d.cost_inr)}
            />
            {data.cost.trend.length > 0 ? (
              <div className="mt-4 flex h-24 items-end gap-1">
                {data.cost.trend.map((day) => (
                  <div key={day.day} className="flex flex-1 flex-col items-center gap-1">
                    <div
                      title={`${day.day}: ${formatInr(day.cost_inr)} · ${day.calls} calls`}
                      className="w-full rounded-t-[4px] bg-indigo/70 transition-all duration-200"
                      style={{ height: `${Math.max(4, (day.cost_inr / maxCost) * 80)}px` }}
                    />
                    <span className="text-[10px] text-ink-subtle">{day.day.slice(5)}</span>
                  </div>
                ))}
              </div>
            ) : (
              // Spend of zero is a real answer, not a missing one: the pipeline
              // ran and nothing reached a model. Say that rather than showing an
              // empty frame.
              <p className="mt-3 text-sm text-ink-muted">
                No model calls in this window — nothing has cost anything yet.
              </p>
            )}
          </div>
        </Card>
      </Reveal>

      <Reveal className="grid gap-4 md:grid-cols-2">
        <Card>
          <FieldLabel>Coverage vs accuracy</FieldLabel>
          <div className="mt-3">
            <NotCalibrated note={data.coverage_accuracy.note} />
          </div>
        </Card>
        <Card>
          <FieldLabel>Calibration</FieldLabel>
          <div className="mt-3">
            <NotCalibrated note={data.calibration.note} />
            <div className="mt-4">
              <FieldLabel>Confidence bands observed</FieldLabel>
              <div className="mt-3">
                <Donut
                  centerValue={String(
                    (["green", "yellow", "red"] as const).reduce(
                      (sum, b) => sum + (data.confidence_bands[b] ?? 0),
                      0,
                    ),
                  )}
                  centerLabel="scored"
                  segments={[
                    {
                      label: "green",
                      value: data.confidence_bands.green ?? 0,
                      className: "stroke-success",
                    },
                    {
                      label: "yellow",
                      value: data.confidence_bands.yellow ?? 0,
                      className: "stroke-warning",
                    },
                    {
                      label: "red",
                      value: data.confidence_bands.red ?? 0,
                      className: "stroke-danger",
                    },
                  ]}
                />
              </div>
            </div>
          </div>
        </Card>
      </Reveal>
    </div>
  );
}
