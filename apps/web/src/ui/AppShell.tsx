// AppShell — the frame every screen sits in.
//
// Dark indigo rail on the left (wordmark, the ten SPEC §17 screens, org at the
// bottom), a top bar carrying tender context + countdown + search + the acting
// role, and a light content well. The rail is the thing that makes this read as
// one product rather than a set of pages.
import { NavLink } from "react-router-dom";
import type { ComponentType, ReactNode } from "react";
import {
  Activity,
  BadgeCheck,
  ChartLine,
  IndianRupee,
  LayoutPanelLeft,
  LogOut,
  PenLine,
  Radar,
  Scale,
  Search,
  Settings,
  Table2,
} from "lucide-react";
import type { OrgSummary } from "../api";
import { CountdownChip } from "./chips";
import { ModeBadge } from "./ModeBadge";
import { OrgBadge } from "./OrgBadge";

export interface NavItem {
  to: string;
  label: string;
  /** A drawn icon. These were Unicode glyphs (◎ ◫ ▤ ₹ ✎) — legible, but they
   *  inherit the text baseline and the font's own metrics, so they never
   *  aligned and never looked deliberate. lucide is the icon set shadcn/ui
   *  ships with, which CLAUDE.md already names in the stack. */
  Icon: ComponentType<{ size?: number | string; className?: string; strokeWidth?: number }>;
  /** Screens that need a tender in context are disabled without one. */
  needsTender?: boolean;
}

// The SPEC §17 screens, in the order Priya meets them. Onboarding is not here:
// adding a company happens on the public landing page, before you have a
// workspace to be inside.
export const NAV_ITEMS: NavItem[] = [
  { to: "/app", label: "Tender Radar", Icon: Radar },
  { to: "/workspace", label: "Workspace", Icon: LayoutPanelLeft, needsTender: true },
  { to: "/matrix", label: "Compliance Matrix", Icon: Table2, needsTender: true },
  { to: "/decision", label: "Decision Room", Icon: IndianRupee, needsTender: true },
  { to: "/proposal", label: "Proposal Studio", Icon: PenLine, needsTender: true },
  { to: "/console", label: "Agent Console", Icon: Activity, needsTender: true },
  { to: "/model-lab", label: "Model Lab", Icon: Scale },
  { to: "/analytics", label: "Analytics", Icon: ChartLine },
  { to: "/evaluation", label: "Evaluation", Icon: BadgeCheck },
  { to: "/admin", label: "Admin", Icon: Settings },
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
      {/* Rail. Below md it collapses to icons: at 375px a 240px rail leaves
          135px of content, which is not a narrow layout, it is a broken one.
          Icons-only keeps every destination reachable without a drawer and
          without any open/closed state to get wrong. */}
      <aside className="on-indigo flex w-14 shrink-0 flex-col bg-indigo text-white md:w-60">
        <div className="flex items-center gap-2.5 px-3 py-4 md:px-5">
          <OrgBadge org={org} size={30} onDark />
          <div className="hidden min-w-0 md:block">
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
            const Icon = item.Icon;
            if (locked) {
              return (
                <span
                  key={item.to}
                  aria-disabled="true"
                  title={`${item.label} — open a tender first`}
                  // white/25 was so faint the five locked screens read as a
                  // rendering fault rather than as "open a tender first".
                  // white/40 is legibly present but clearly not available.
                  className="mb-0.5 flex cursor-not-allowed items-center justify-center gap-2.5 rounded-[8px] px-3 py-2 text-sm text-white/40 md:justify-start"
                >
                  <Icon size={16} strokeWidth={1.75} className="shrink-0" />
                  <span className="hidden md:inline">{item.label}</span>
                </span>
              );
            }
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/app"}
                title={item.label}
                className={({ isActive }) =>
                  // The active item gets a left marker as well as a fill. On a
                  // dark rail a background alone is a weak signal at a glance,
                  // and this is the only "where am I" cue the product has.
                  `group relative mb-0.5 flex items-center justify-center gap-2.5 rounded-[8px] px-3 py-2 text-sm transition-colors duration-150 md:justify-start ${
                    isActive
                      ? "bg-white/12 font-medium text-white"
                      : "text-white/65 hover:bg-white/8 hover:text-white"
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <span
                      aria-hidden
                      className={`absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-accent transition-opacity duration-150 ${
                        isActive ? "opacity-100" : "opacity-0"
                      }`}
                    />
                    <Icon
                      size={16}
                      strokeWidth={isActive ? 2 : 1.75}
                      className="shrink-0"
                    />
                    <span className="hidden md:inline">{item.label}</span>
                  </>
                )}
              </NavLink>
            );
          })}
        </nav>

        <div className="border-t border-white/10 px-2 py-3 md:px-4">
          <div className="flex items-center justify-center gap-2 md:justify-start">
            <span className="hidden md:block">
              <OrgBadge org={org} size={26} onDark />
            </span>
            <span className="hidden min-w-0 flex-1 truncate text-xs text-white/80 md:block"
                  title={org.name}>
              {org.name}
            </span>
            {onSignOut && (
              <button
                data-testid="sign-out"
                onClick={onSignOut}
                title="Sign out and choose another company"
                aria-label="Sign out"
                className="rounded-[8px] p-1.5 text-white/50 transition-colors duration-150 hover:bg-white/10 hover:text-white"
              >
                <LogOut size={15} strokeWidth={1.75} />
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
            <div className="relative hidden md:block">
              <Search
                size={14}
                strokeWidth={1.75}
                aria-hidden
                className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-subtle"
              />
              <input
                type="search"
                placeholder="Search tenders…"
                onChange={(e) => onSearch(e.target.value)}
                className="w-56 rounded-[8px] border border-hairline bg-surface py-1.5 pl-8 pr-2.5 text-sm text-ink transition-colors duration-150 placeholder:text-ink-subtle hover:border-ink-subtle/40"
              />
            </div>
          )}
          <ModeBadge />
          {right}
        </header>

        <main className="min-h-0 flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  );
}
