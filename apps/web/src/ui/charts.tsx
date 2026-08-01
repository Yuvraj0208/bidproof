// Chart primitives — hand-drawn SVG, no charting dependency.
//
// Three reasons this is not recharts or d3:
//
// 1. **The air-gapped rule.** index.css already records that this must run on a
//    machine with no network. Fewer moving parts is fewer things to vendor.
// 2. **The numbers matter more than the shapes.** Every chart here renders its
//    value as real text as well as geometry, so a screen reader reads it, a
//    test can assert it, and a CTO squinting at a projector can read it. A
//    library would fight us on that.
// 3. **Tabular discipline.** The rest of the product uses tabular numerals so
//    figures never jitter. Hand-drawn axes keep that, and keep the financial
//    feel the tables already have.
//
// Everything is deliberately plain: values in, SVG out, no internal state, no
// tooltips that hide data behind a hover. If a number is worth drawing it is
// worth showing.
import { motion, useReducedMotion } from "framer-motion";
import type { ReactNode } from "react";

import { EASE } from "./motion";

/** Shared: turn a value into a bar length without dividing by zero. */
function ratio(value: number, max: number): number {
  return max > 0 ? Math.max(0, Math.min(1, value / max)) : 0;
}

function Grow({
  children,
  delay = 0,
  originX = 0,
}: {
  children: ReactNode;
  delay?: number;
  originX?: number;
}) {
  const still = useReducedMotion();
  if (still) return <>{children}</>;
  return (
    <motion.g
      initial={{ scaleX: 0, opacity: 0.4 }}
      animate={{ scaleX: 1, opacity: 1 }}
      transition={{ duration: 0.5, delay, ease: EASE }}
      style={{ originX }}
    >
      {children}
    </motion.g>
  );
}

/* ------------------------------------------------------------- Sparkline */

/** A trend, small enough to sit inside a stat card.
 *
 *  Used for the daily cost trend: the shape answers "is this going up?" at a
 *  glance, and the caller still prints the actual figure beside it.
 */
export function Sparkline({
  values,
  width = 120,
  height = 32,
  className = "text-indigo",
  label,
}: {
  values: number[];
  width?: number;
  height?: number;
  className?: string;
  label?: string;
}) {
  const still = useReducedMotion();
  if (values.length < 2) {
    return (
      <svg width={width} height={height} role="img" aria-label={label ?? "no trend yet"}>
        <line
          x1={0} y1={height / 2} x2={width} y2={height / 2}
          stroke="currentColor" strokeDasharray="3 3"
          className="text-hairline"
        />
      </svg>
    );
  }

  const max = Math.max(...values);
  const min = Math.min(...values);
  const span = max - min || 1;
  const step = width / (values.length - 1);
  const points = values.map((v, i) => {
    const x = i * step;
    // Inset by 2px top and bottom so the stroke is never clipped.
    const y = height - 2 - ratio(v - min, span) * (height - 4);
    return `${x},${y}`;
  });

  return (
    <svg
      width={width}
      height={height}
      className={className}
      role="img"
      aria-label={label ?? `trend across ${values.length} points`}
    >
      <motion.polyline
        points={points.join(" ")}
        fill="none"
        stroke="currentColor"
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        initial={still ? undefined : { pathLength: 0 }}
        animate={still ? undefined : { pathLength: 1 }}
        transition={{ duration: 0.7, ease: EASE }}
      />
      <circle
        cx={(values.length - 1) * step}
        cy={height - 2 - ratio(values[values.length - 1] - min, span) * (height - 4)}
        r={2.5}
        fill="currentColor"
      />
    </svg>
  );
}

/* ------------------------------------------------------------ BarSeries */

/** Horizontal bars with the label and the value as text.
 *
 *  Replaces the CSS-width bars in Analytics. The gain over a div is not
 *  prettiness — it is that the value, the axis and the bar are one object, so
 *  they cannot drift apart.
 */
export function BarSeries({
  data,
  fill = "fill-indigo",
  formatValue = (n: number) => n.toLocaleString("en-IN"),
}: {
  // `fill` is a COMPLETE Tailwind class, never a fragment. Tailwind v4 scans
  // source for literal class names, so `fill-${tone}` would compile to nothing
  // and the bars would be invisible — the kind of bug that only shows up in a
  // production build.
  data: { label: string; value: number; fill?: string }[];
  fill?: string;
  formatValue?: (n: number) => string;
}) {
  const max = Math.max(...data.map((d) => d.value), 1);

  return (
    <div data-testid="bar-series" className="space-y-2.5">
      {data.map((row, i) => (
        <div key={row.label}>
          <div className="mb-1 flex items-baseline justify-between text-xs">
            <span className="text-ink-muted">{row.label}</span>
            <span data-numeric className="font-medium text-ink">
              {formatValue(row.value)}
            </span>
          </div>
          <svg width="100%" height={8} role="presentation" className="block">
            <rect
              x={0} y={0} width="100%" height={8} rx={4}
              className="fill-surface"
            />
            <Grow delay={i * 0.05}>
              <rect
                x={0}
                y={0}
                width={`${ratio(row.value, max) * 100}%`}
                height={8}
                rx={4}
                className={row.fill ?? fill}
              />
            </Grow>
          </svg>
        </div>
      ))}
    </div>
  );
}

/* ---------------------------------------------------------------- Funnel */

/** The discovery funnel: discovered → triaged → parsed → checked → decided.
 *
 *  Drawn as narrowing bars because the story is attrition — how many tenders
 *  survive each stage. The drop between two stages is the interesting number,
 *  so it is printed rather than left to be inferred from the widths.
 */
export function Funnel({
  stages,
}: {
  stages: { stage: string; count: number }[];
}) {
  const max = Math.max(...stages.map((s) => s.count), 1);

  return (
    <div data-testid="funnel" className="space-y-1.5">
      {stages.map((s, i) => {
        const previous = i > 0 ? stages[i - 1].count : null;
        const dropped = previous !== null ? previous - s.count : null;
        return (
          <div key={s.stage} className="flex items-center gap-3">
            <span className="w-24 shrink-0 text-xs text-ink-muted">{s.stage}</span>
            <svg height={22} width="100%" role="presentation" className="block flex-1">
              <rect x={0} y={0} width="100%" height={22} rx={5} className="fill-surface" />
              <Grow delay={i * 0.06}>
                <rect
                  x={0} y={0}
                  width={`${ratio(s.count, max) * 100}%`}
                  height={22} rx={5}
                  className="fill-indigo"
                />
              </Grow>
            </svg>
            <span data-numeric className="w-10 shrink-0 text-right text-xs font-medium text-ink">
              {s.count}
            </span>
            <span className="w-16 shrink-0 text-right text-[11px] text-ink-subtle">
              {dropped ? `−${dropped}` : ""}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/* ----------------------------------------------------------------- Donut */

/** Proportions — confidence bands, verdict mix.
 *
 *  A donut rather than a pie so the total can live in the middle, which is
 *  usually the number the reader actually wants.
 */
export function Donut({
  segments,
  size = 132,
  centerLabel,
  centerValue,
}: {
  segments: { label: string; value: number; className: string }[];
  size?: number;
  centerLabel?: string;
  centerValue?: string;
}) {
  const still = useReducedMotion();
  const total = segments.reduce((sum, s) => sum + s.value, 0);
  const radius = size / 2 - 12;
  const circumference = 2 * Math.PI * radius;

  let consumed = 0;

  return (
    <div className="flex items-center gap-5">
      <svg
        width={size}
        height={size}
        role="img"
        aria-label={
          total
            ? segments.map((s) => `${s.label}: ${s.value}`).join(", ")
            : "nothing measured yet"
        }
      >
        <g transform={`translate(${size / 2} ${size / 2}) rotate(-90)`}>
          <circle
            r={radius} fill="none" strokeWidth={12}
            className="stroke-surface"
          />
          {total > 0 &&
            segments.map((seg, i) => {
              const length = (seg.value / total) * circumference;
              const offset = consumed;
              consumed += length;
              return (
                <motion.circle
                  key={seg.label}
                  r={radius}
                  fill="none"
                  strokeWidth={12}
                  className={seg.className}
                  strokeDasharray={`${length} ${circumference - length}`}
                  strokeDashoffset={-offset}
                  initial={still ? undefined : { opacity: 0 }}
                  animate={still ? undefined : { opacity: 1 }}
                  transition={{ delay: i * 0.08, duration: 0.4, ease: EASE }}
                />
              );
            })}
        </g>
        {centerValue && (
          <text
            x="50%" y="50%" textAnchor="middle"
            className="fill-ink text-[15px] font-semibold"
            dy="0.05em"
            data-numeric
          >
            {centerValue}
          </text>
        )}
        {centerLabel && (
          <text
            x="50%" y="50%" textAnchor="middle"
            className="fill-ink-subtle text-[10px]"
            dy="1.5em"
          >
            {centerLabel}
          </text>
        )}
      </svg>

      <ul className="space-y-1.5 text-xs">
        {segments.map((seg) => (
          <li key={seg.label} className="flex items-center gap-2">
            <span
              aria-hidden
              className={`h-2.5 w-2.5 rounded-full ${seg.className.replace("stroke-", "bg-")}`}
            />
            <span className="text-ink-muted">{seg.label}</span>
            <span data-numeric className="font-medium text-ink">{seg.value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* ------------------------------------------------------------- MetricBar */

/** One measurement against its target — the shape the Evaluation screen needs.
 *
 *  Direction matters: a character error rate of 0.02 is excellent and an
 *  accuracy of 0.02 is a disaster. `higherIsBetter` decides the colour, because
 *  a rate coloured like an accuracy is a lie told in green.
 */
export function MetricBar({
  value,
  target,
  higherIsBetter = true,
  label,
}: {
  value: number | null;
  target?: number | null;
  higherIsBetter?: boolean;
  label?: string;
}) {
  if (value === null) {
    return (
      <div className="h-2 w-full rounded-[8px] border border-dashed border-hairline" />
    );
  }
  const meets =
    target == null ? null : higherIsBetter ? value >= target : value <= target;
  const tone =
    meets === null ? "fill-indigo" : meets ? "fill-success" : "fill-warning";

  return (
    <svg
      width="100%" height={8} className="block"
      role="img"
      aria-label={label ?? `${Math.round(value * 100)} percent`}
    >
      <rect x={0} y={0} width="100%" height={8} rx={4} className="fill-surface" />
      <Grow>
        <rect
          x={0} y={0}
          width={`${ratio(value, 1) * 100}%`}
          height={8} rx={4}
          className={tone}
        />
      </Grow>
      {target != null && (
        // The target as a tick on the bar: "where we need to be" is more useful
        // than the bare number, and it survives the value changing.
        <rect
          x={`${ratio(target, 1) * 100}%`}
          y={-2} width={2} height={12}
          className="fill-ink-subtle"
        />
      )}
    </svg>
  );
}
