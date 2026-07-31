// The design system's structural primitives (SPEC §17).
// Behaviour lives in screens; these own only shape, spacing and tone, so a
// screen that uses them is consistent by default rather than by discipline.
import { motion } from "framer-motion";
import type { ReactNode } from "react";

/** Card — the resting surface. Everything on the light background sits here. */
export function Card({
  children,
  className = "",
  padded = true,
  as: Tag = "div",
}: {
  children: ReactNode;
  className?: string;
  padded?: boolean;
  as?: "div" | "section" | "article";
}) {
  return (
    <Tag
      className={`rounded-[12px] border border-hairline bg-white shadow-card ${
        padded ? "p-4" : ""
      } ${className}`}
    >
      {children}
    </Tag>
  );
}

/** PageHeader — every screen opens the same way: what this is, then the
 *  default next action on the right (SPEC §17: answer "what do I do next?"). */
export function PageHeader({
  title,
  subtitle,
  actions,
  meta,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  meta?: ReactNode;
}) {
  return (
    <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0">
        <h1 className="truncate text-xl font-semibold tracking-[-0.01em] text-ink">
          {title}
        </h1>
        {subtitle && (
          <p className="mt-1 text-sm text-ink-muted">{subtitle}</p>
        )}
        {meta && <div className="mt-2 flex flex-wrap gap-2">{meta}</div>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </header>
  );
}

/** StatCallout — one number that matters, with its unit and a why-line.
 *  Used for the EV terms and the Agent Console totals. */
export function StatCallout({
  label,
  value,
  hint,
  tone = "neutral",
  size = "md",
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  tone?: "neutral" | "success" | "warning" | "danger" | "brand";
  size?: "md" | "lg";
}) {
  const tones: Record<string, string> = {
    neutral: "text-ink",
    success: "text-success",
    warning: "text-warning",
    danger: "text-danger",
    brand: "text-indigo",
  };
  return (
    <div data-testid="stat-callout" className="min-w-0">
      <div className="text-xs font-medium uppercase tracking-wide text-ink-subtle">
        {label}
      </div>
      <div
        data-numeric
        className={`mt-1 font-semibold tracking-[-0.02em] ${tones[tone]} ${
          size === "lg" ? "text-3xl" : "text-xl"
        }`}
      >
        {value}
      </div>
      {hint && <div className="mt-1 text-xs text-ink-muted">{hint}</div>}
    </div>
  );
}

/** EmptyState — teaches rather than apologises (SPEC §17). Always offers the
 *  action that would fill it. */
export function EmptyState({
  title,
  body,
  action,
  icon = "◎",
}: {
  title: string;
  body: string;
  action?: ReactNode;
  icon?: string;
}) {
  return (
    <div
      data-testid="empty-state"
      className="flex flex-col items-center justify-center rounded-[12px] border border-dashed border-hairline bg-white/60 px-6 py-12 text-center"
    >
      <div aria-hidden className="mb-3 text-2xl text-ink-subtle">{icon}</div>
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      <p className="mt-1 max-w-md text-sm text-ink-muted">{body}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

/** SkeletonLoader — the shape of the content that is coming, never a spinner
 *  (a spinner tells you nothing about what to expect). */
export function SkeletonLoader({
  rows = 3,
  className = "",
}: {
  rows?: number;
  className?: string;
}) {
  return (
    <div data-testid="skeleton" className={`space-y-2 ${className}`} aria-hidden>
      {Array.from({ length: rows }).map((_, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0.45 }}
          animate={{ opacity: [0.45, 0.75, 0.45] }}
          transition={{ duration: 1.4, repeat: Infinity, delay: i * 0.08 }}
          className="h-4 rounded-[8px] bg-hairline"
          style={{ width: `${92 - i * 11}%` }}
        />
      ))}
    </div>
  );
}

/** Button — one primary per view; the rest are quiet. */
export function Button({
  children,
  variant = "secondary",
  size = "md",
  className = "",
  ...rest
}: {
  children: ReactNode;
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md";
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const variants: Record<string, string> = {
    primary:
      "bg-indigo text-white hover:bg-indigo-active border border-transparent",
    secondary:
      "bg-white text-ink border border-hairline hover:bg-indigo-tint hover:border-indigo/20",
    ghost: "bg-transparent text-ink-muted border border-transparent hover:bg-indigo-tint",
    danger: "bg-danger text-white border border-transparent hover:brightness-110",
  };
  return (
    <button
      {...rest}
      className={`inline-flex items-center gap-1.5 rounded-[8px] font-medium transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-45 ${
        size === "sm" ? "px-2.5 py-1 text-xs" : "px-3 py-1.5 text-sm"
      } ${variants[variant]} ${className}`}
    >
      {children}
    </button>
  );
}

/** Section label used across panels — small, quiet, consistent. */
export function FieldLabel({ children }: { children: ReactNode }) {
  return (
    <span className="text-xs font-medium uppercase tracking-wide text-ink-subtle">
      {children}
    </span>
  );
}

/** ReadingIndicator — a document being read, right now.
 *
 * The SkeletonLoader above is for content whose *shape* we know is coming. This
 * is the other case: a background job of unknown length, where the honest thing
 * to show is motion plus the page count so far. A tender that is mid-parse used
 * to be invisible in the product entirely, which read as "my upload vanished".
 */
export function ReadingIndicator({
  label = "Reading the document",
  detail,
}: {
  label?: string;
  detail?: string;
}) {
  return (
    <div
      data-testid="reading-indicator"
      className="flex items-center gap-2.5"
      role="status"
      aria-live="polite"
    >
      <motion.span
        aria-hidden
        className="block h-3.5 w-3.5 shrink-0 rounded-full border-[1.5px] border-indigo/25 border-t-indigo"
        animate={{ rotate: 360 }}
        transition={{ duration: 0.9, repeat: Infinity, ease: "linear" }}
      />
      <span className="min-w-0">
        <span className="text-xs font-medium text-indigo">{label}</span>
        {/* Three pages turning: motion that means "working through it". */}
        <span aria-hidden className="ml-1.5 inline-flex gap-0.5 align-middle">
          {[0, 1, 2].map((i) => (
            <motion.span
              key={i}
              className="block h-1 w-1 rounded-full bg-indigo/50"
              animate={{ opacity: [0.25, 1, 0.25] }}
              transition={{
                duration: 1.2,
                repeat: Infinity,
                delay: i * 0.18,
                ease: "easeInOut",
              }}
            />
          ))}
        </span>
        {detail && (
          <span className="ml-2 text-[11px] text-ink-muted">{detail}</span>
        )}
      </span>
    </div>
  );
}
