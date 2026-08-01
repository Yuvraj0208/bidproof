// Product artwork — every mark here is drawn from something BidProof actually
// does, never from a stock library.
//
// The rule: if you cannot name the product behaviour a drawing depicts, it does
// not belong. A tender page with a proof box landing on a clause; a balance
// weighing rupees against risk; the Conductor's parallel branch. Someone who
// has used the product should recognise each one; someone who has not should
// learn something from it.
//
// All of it is inline SVG using `currentColor`, so the same drawing works on
// the light surface and on the void without a second asset.
import type { ReactNode } from "react";

/* --------------------------------------------------------- WindowFrame */

/** Browser chrome around a screenshot or a live panel.
 *
 *  The reference sites all do this and it is not decoration: a product shot
 *  floating on a page reads as a mockup, while the same shot in a window reads
 *  as software that exists. Used on the landing page and in the docs.
 */
export function WindowFrame({
  children,
  label,
  tone = "dark",
  className = "",
}: {
  children: ReactNode;
  /** The address-bar text — a route, so it says where in the product you are. */
  label?: string;
  tone?: "dark" | "light";
  className?: string;
}) {
  const dark = tone === "dark";
  return (
    <div
      className={`overflow-hidden rounded-[12px] border ${
        dark
          ? "border-void-line bg-void-raised shadow-glow"
          : "border-hairline bg-white shadow-overlay"
      } ${className}`}
    >
      <div
        className={`flex items-center gap-2 border-b px-3 py-2 ${
          dark ? "border-void-line" : "border-hairline"
        }`}
      >
        <span aria-hidden className="flex gap-1.5">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className={`h-2.5 w-2.5 rounded-full ${
                dark ? "bg-white/15" : "bg-hairline"
              }`}
            />
          ))}
        </span>
        {label && (
          <span
            className={`ml-2 truncate font-mono text-[11px] ${
              dark ? "text-white/40" : "text-ink-subtle"
            }`}
          >
            {label}
          </span>
        )}
      </div>
      {children}
    </div>
  );
}

/* ------------------------------------------------------- Empty-state art */

/** A tender page with the proof box landing on the clause that matters.
 *
 *  The product's whole promise in one drawing: every fact clicks back to a page
 *  and a box. Used wherever rules or proof are missing.
 */
export function ProofArt({ className = "", size = 120 }: { className?: string; size?: number }) {
  return (
    <svg
      viewBox="0 0 120 96" width={size} height={size * 0.8}
      className={className} role="img"
      aria-label="a tender page with one clause highlighted as proof"
    >
      <rect
        x={14} y={6} width={78} height={84} rx={6}
        className="fill-white stroke-hairline" strokeWidth={1.5}
      />
      {[18, 28, 48, 58, 68].map((y) => (
        <rect
          key={y} x={24} y={y} width={y === 58 ? 44 : 58} height={4} rx={2}
          className="fill-hairline"
        />
      ))}
      {/* The cited clause, and the box that proves it. */}
      <rect x={24} y={36} width={52} height={5} rx={2.5} className="fill-ink-muted" />
      <rect
        x={20} y={32} width={62} height={13} rx={3}
        className="fill-warning/15 stroke-warning" strokeWidth={1.5}
      />
      <circle cx={96} cy={38} r={9} className="fill-warning" />
      <path
        d="M92 38l3 3 5-6" fill="none" stroke="white"
        strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round"
      />
    </svg>
  );
}

/** A balance weighing rupees against risk — the Decider's job.
 *
 *  Used on the Decision Room before a decision exists, and anywhere expected
 *  value is the missing thing.
 */
export function LedgerArt({ className = "", size = 120 }: { className?: string; size?: number }) {
  return (
    <svg
      viewBox="0 0 120 96" width={size} height={size * 0.8}
      className={className} role="img"
      aria-label="a balance weighing expected value against risk"
    >
      <rect x={58} y={22} width={4} height={56} rx={2} className="fill-ink-subtle" />
      <rect x={40} y={78} width={40} height={5} rx={2.5} className="fill-ink-subtle" />
      <rect x={26} y={20} width={68} height={4} rx={2} className="fill-ink-muted" />
      {/* Left pan: money. Sits lower — the bid is worth taking. */}
      <path d="M26 24l-10 18h34z" className="fill-success/20 stroke-success" strokeWidth={1.5} />
      <text
        x={33} y={39} textAnchor="middle"
        className="fill-success text-[13px] font-semibold"
      >
        ₹
      </text>
      {/* Right pan: risk. */}
      <path d="M94 24l-9 14h26z" className="fill-warning/20 stroke-warning" strokeWidth={1.5} />
      <path
        d="M94 28v5m0 3v1" stroke="currentColor"
        className="text-warning" strokeWidth={1.8} strokeLinecap="round"
      />
    </svg>
  );
}

/** The Conductor's graph, with its parallel branch.
 *
 *  Deliberately the same shape the Agent Console draws from the compiled graph,
 *  so the illustration and the real thing agree.
 */
export function GraphArt({ className = "", size = 120 }: { className?: string; size?: number }) {
  return (
    <svg
      viewBox="0 0 120 96" width={size} height={size * 0.8}
      className={className} role="img"
      aria-label="a pipeline whose two middle steps run at the same time"
    >
      <g className="stroke-hairline" strokeWidth={1.5} fill="none">
        <path d="M28 48h14M64 33h14M64 63h14M50 40v-7h14M50 56v7h14" />
      </g>
      <rect x={8} y={40} width={20} height={16} rx={4} className="fill-indigo-tint stroke-indigo" strokeWidth={1.5} />
      {/* The pair that runs concurrently. */}
      <rect x={64} y={25} width={22} height={16} rx={4} className="fill-indigo-tint stroke-indigo" strokeWidth={1.5} />
      <rect x={64} y={55} width={22} height={16} rx={4} className="fill-indigo-tint stroke-indigo" strokeWidth={1.5} />
      {/* The human checkpoint: a different shape, because it is a different kind
          of step — the graph has no path around it. */}
      <path
        d="M96 40h12l4 8-4 8H96l4-8z"
        className="fill-warning/20 stroke-warning" strokeWidth={1.5}
      />
    </svg>
  );
}

/** A radar sweep over scattered tenders — discovery with nothing found yet. */
export function RadarArt({ className = "", size = 120 }: { className?: string; size?: number }) {
  return (
    <svg
      viewBox="0 0 120 96" width={size} height={size * 0.8}
      className={className} role="img"
      aria-label="a radar sweep looking for tenders"
    >
      {[30, 22, 14].map((r) => (
        <circle
          key={r} cx={60} cy={48} r={r}
          className="fill-none stroke-hairline" strokeWidth={1.5}
        />
      ))}
      <path
        d="M60 48L84 30a30 30 0 0 1 6 18z"
        className="fill-indigo/15"
      />
      <line
        x1={60} y1={48} x2={84} y2={30}
        className="stroke-indigo" strokeWidth={1.5} strokeLinecap="round"
      />
      <circle cx={60} cy={48} r={3} className="fill-indigo" />
      {[[76, 40], [48, 32], [66, 64]].map(([cx, cy]) => (
        <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r={2.5} className="fill-ink-subtle" />
      ))}
    </svg>
  );
}

/** A document with a hard stop across it — the export blocker. */
export function BlockedArt({ className = "", size = 120 }: { className?: string; size?: number }) {
  return (
    <svg
      viewBox="0 0 120 96" width={size} height={size * 0.8}
      className={className} role="img"
      aria-label="an export refused until its blockers are cleared"
    >
      <rect
        x={26} y={8} width={68} height={80} rx={6}
        className="fill-white stroke-hairline" strokeWidth={1.5}
      />
      {[20, 30, 40, 50, 60, 70].map((y) => (
        <rect
          key={y} x={36} y={y} width={y === 70 ? 28 : 48} height={4} rx={2}
          className="fill-hairline"
        />
      ))}
      <circle cx={60} cy={48} r={20} className="fill-danger-tint stroke-danger" strokeWidth={2} />
      <line
        x1={47} y1={48} x2={73} y2={48}
        className="stroke-danger" strokeWidth={3} strokeLinecap="round"
      />
    </svg>
  );
}

/** A page becoming structured elements — parsing, in progress or absent. */
export function ParseArt({ className = "", size = 120 }: { className?: string; size?: number }) {
  return (
    <svg
      viewBox="0 0 120 96" width={size} height={size * 0.8}
      className={className} role="img"
      aria-label="a scanned page being turned into structured elements"
    >
      <rect
        x={10} y={14} width={44} height={68} rx={5}
        className="fill-white stroke-hairline" strokeWidth={1.5}
      />
      {[24, 32, 40, 48, 56, 64].map((y) => (
        <rect key={y} x={18} y={y} width={28} height={3.5} rx={1.75} className="fill-hairline" />
      ))}
      <path
        d="M58 48h10m0 0l-4-4m4 4l-4 4"
        className="stroke-ink-subtle" strokeWidth={1.5}
        strokeLinecap="round" strokeLinejoin="round" fill="none"
      />
      {[[74, 20], [74, 38], [74, 56], [74, 70]].map(([x, y], i) => (
        <rect
          key={y} x={x} y={y} width={36} height={i === 3 ? 10 : 12} rx={3}
          className="fill-indigo-tint stroke-indigo" strokeWidth={1.2}
        />
      ))}
    </svg>
  );
}

/** The BidProof mark — a proof box over a page corner. Used at small sizes
 *  where the full wordmark would not read. */
export function Mark({ size = 28, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32" width={size} height={size}
      className={className} role="img" aria-label="BidProof"
    >
      <rect x={4} y={2} width={20} height={28} rx={4} className="fill-current opacity-25" />
      <rect
        x={10} y={13} width={18} height={11} rx={3}
        className="fill-none stroke-current" strokeWidth={2.5}
      />
      <path
        d="M14 18.5l2.5 2.5 5-5.5" fill="none"
        className="stroke-current" strokeWidth={2.5}
        strokeLinecap="round" strokeLinejoin="round"
      />
    </svg>
  );
}
