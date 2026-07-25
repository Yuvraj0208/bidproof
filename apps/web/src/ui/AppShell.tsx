// AppShell — the frame every screen sits in.
//
// Dark indigo rail on the left (wordmark, the ten SPEC §17 screens, org at the
// bottom), a top bar carrying tender context + countdown + search + the acting
// role, and a light content well. The rail is the thing that makes this read as
// one product rather than a set of pages.
import { NavLink } from "react-router-dom";
import type { ReactNode } from "react";
import { CountdownChip } from "./chips";
import { ModeBadge } from "./ModeBadge";

export interface NavItem {
  to: string;
  label: string;
  glyph: string;
  /** Screens that need a tender in context are disabled without one. */
  needsTender?: boolean;
}

// The ten screens of SPEC §17, in the order Priya meets them.
export const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Tender Radar", glyph: "◎" },
  { to: "/workspace", label: "Workspace", glyph: "◫", needsTender: true },
  { to: "/matrix", label: "Compliance Matrix", glyph: "▤", needsTender: true },
  { to: "/decision", label: "Decision Room", glyph: "₹", needsTender: true },
  { to: "/proposal", label: "Proposal Studio", glyph: "✎", needsTender: true },
  { to: "/console", label: "Agent Console", glyph: "◷", needsTender: true },
  { to: "/model-lab", label: "Model Lab", glyph: "⚖" },
  { to: "/analytics", label: "Analytics", glyph: "◭" },
  { to: "/admin", label: "Admin", glyph: "⚙" },
  { to: "/onboarding", label: "Onboarding", glyph: "✦" },
];

export function AppShell({
  children,
  orgName,
  tenderTitle,
  closingAt,
  right,
  onSearch,
}: {
  children: ReactNode;
  orgName: string;
  tenderTitle?: string | null;
  closingAt?: string | null;
  right?: ReactNode;
  onSearch?: (query: string) => void;
}) {
  return (
    <div className="flex h-screen overflow-hidden bg-surface">
      {/* Rail */}
      <aside className="on-indigo flex w-60 shrink-0 flex-col bg-indigo text-white">
        <div className="px-5 py-4">
          <div className="text-base font-semibold tracking-[-0.01em]">
            BidProof
          </div>
          <div className="mt-0.5 text-[11px] text-white/55">
            Proof for every claim
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto px-2 py-2">
          {NAV_ITEMS.map((item) => {
            const locked = item.needsTender && !tenderTitle;
            if (locked) {
              return (
                <span
                  key={item.to}
                  aria-disabled="true"
                  title="Open a tender first"
                  className="mb-0.5 flex cursor-not-allowed items-center gap-2.5 rounded-[8px] px-3 py-2 text-sm text-white/30"
                >
                  <span aria-hidden className="w-4 text-center">{item.glyph}</span>
                  {item.label}
                </span>
              );
            }
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  `mb-0.5 flex items-center gap-2.5 rounded-[8px] px-3 py-2 text-sm transition-colors duration-150 ${
                    isActive
                      ? "bg-white/12 font-medium text-white"
                      : "text-white/70 hover:bg-white/8 hover:text-white"
                  }`
                }
              >
                <span aria-hidden className="w-4 text-center">{item.glyph}</span>
                {item.label}
              </NavLink>
            );
          })}
        </nav>

        <div className="border-t border-white/10 px-5 py-3">
          <div className="text-[11px] uppercase tracking-wide text-white/45">
            Organisation
          </div>
          <div className="truncate text-sm text-white/90" title={orgName}>
            {orgName || "No organisation"}
          </div>
        </div>
      </aside>

      {/* Content */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-hairline bg-white px-5">
          <div className="min-w-0 flex-1">
            {tenderTitle ? (
              <div className="flex items-center gap-2">
                <span className="truncate text-sm font-medium text-ink" title={tenderTitle}>
                  {tenderTitle}
                </span>
                <CountdownChip closingAt={closingAt ?? null} />
              </div>
            ) : (
              <span className="text-sm text-ink-subtle">No tender selected</span>
            )}
          </div>

          {onSearch && (
            <input
              type="search"
              placeholder="Search tenders…"
              onChange={(e) => onSearch(e.target.value)}
              className="hidden w-56 rounded-[8px] border border-hairline bg-surface px-2.5 py-1.5 text-sm text-ink placeholder:text-ink-subtle md:block"
            />
          )}
          <ModeBadge />
          {right}
        </header>

        <main className="min-h-0 flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  );
}
