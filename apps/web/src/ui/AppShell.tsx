// AppShell — the frame every screen sits in.
//
// Dark indigo rail on the left (wordmark, the ten SPEC §17 screens, org at the
// bottom), a top bar carrying tender context + countdown + search + the acting
// role, and a light content well. The rail is the thing that makes this read as
// one product rather than a set of pages.
import { NavLink } from "react-router-dom";
import type { ReactNode } from "react";
import type { OrgSummary } from "../api";
import { CountdownChip } from "./chips";
import { ModeBadge } from "./ModeBadge";
import { OrgBadge } from "./OrgBadge";

export interface NavItem {
  to: string;
  label: string;
  glyph: string;
  /** Screens that need a tender in context are disabled without one. */
  needsTender?: boolean;
}

// The SPEC §17 screens, in the order Priya meets them. Onboarding is not here:
// adding a company happens on the public landing page, before you have a
// workspace to be inside.
export const NAV_ITEMS: NavItem[] = [
  { to: "/app", label: "Tender Radar", glyph: "◎" },
  { to: "/workspace", label: "Workspace", glyph: "◫", needsTender: true },
  { to: "/matrix", label: "Compliance Matrix", glyph: "▤", needsTender: true },
  { to: "/decision", label: "Decision Room", glyph: "₹", needsTender: true },
  { to: "/proposal", label: "Proposal Studio", glyph: "✎", needsTender: true },
  { to: "/console", label: "Agent Console", glyph: "◷", needsTender: true },
  { to: "/model-lab", label: "Model Lab", glyph: "⚖" },
  { to: "/analytics", label: "Analytics", glyph: "◭" },
  { to: "/evaluation", label: "Evaluation", glyph: "✓" },
  { to: "/admin", label: "Admin", glyph: "⚙" },
];

export function AppShell({
  children,
  org,
  tenderTitle,
  closingAt,
  right,
  onSearch,
  onSignOut,
}: {
  children: ReactNode;
  /** The signed-in company — its mark and name brand the whole shell. */
  org: Pick<OrgSummary, "name" | "branding">;
  tenderTitle?: string | null;
  closingAt?: string | null;
  right?: ReactNode;
  onSearch?: (query: string) => void;
  onSignOut?: () => void;
}) {
  return (
    <div className="flex h-screen overflow-hidden bg-surface">
      {/* Rail */}
      <aside className="on-indigo flex w-60 shrink-0 flex-col bg-indigo text-white">
        <div className="flex items-center gap-2.5 px-5 py-4">
          <OrgBadge org={org} size={30} onDark />
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold tracking-[-0.01em]"
                 title={org.name}>
              {org.name}
            </div>
            <div className="text-[11px] text-white/45">BidProof</div>
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
                end={item.to === "/app"}
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

        <div className="border-t border-white/10 px-4 py-3">
          <div className="flex items-center gap-2">
            <OrgBadge org={org} size={26} onDark />
            <span className="min-w-0 flex-1 truncate text-xs text-white/80"
                  title={org.name}>
              {org.name}
            </span>
            {onSignOut && (
              <button
                data-testid="sign-out"
                onClick={onSignOut}
                title="Sign out and choose another company"
                className="rounded-[8px] px-2 py-1 text-[11px] text-white/60 transition-colors duration-150 hover:bg-white/10 hover:text-white"
              >
                Sign out
              </button>
            )}
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
