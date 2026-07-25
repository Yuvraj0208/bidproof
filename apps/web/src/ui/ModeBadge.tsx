// Is real intelligence actually on? (FINISH_STATUS D9.)
//
// A template answer that looks like a model answer is how a shallow output
// reaches a customer unnoticed — so the mode is always on screen, and when it
// degrades the badge says what to DO about it, not just that something is wrong.
import { useEffect, useState } from "react";
import { fetchModelHealth, type ModelHealth } from "../api";
import { Tooltip } from "./overlays";

export function ModeBadge({ poll = true }: { poll?: boolean }) {
  const [health, setHealth] = useState<ModelHealth | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = () =>
      fetchModelHealth()
        .then((h) => alive && (setHealth(h), setFailed(false)))
        .catch(() => alive && setFailed(true));
    load();
    if (!poll) return () => { alive = false; };
    const timer = window.setInterval(load, 60_000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, [poll]);

  if (failed) {
    return (
      <span
        data-testid="mode-badge"
        className="inline-flex items-center gap-1.5 rounded-[8px] border border-danger/25 bg-danger-tint px-2 py-0.5 text-xs font-medium text-danger"
      >
        <span aria-hidden>●</span> API unreachable
      </span>
    );
  }

  if (!health) {
    return (
      <span
        data-testid="mode-badge"
        className="inline-flex items-center gap-1.5 rounded-[8px] border border-hairline bg-white px-2 py-0.5 text-xs text-ink-subtle"
      >
        Checking…
      </span>
    );
  }

  const broken = Object.entries(health.roles)
    .filter(([, v]) => !v.ok)
    .map(([role, v]) => `${role}: ${v.error ?? "unavailable"}`);

  const styles: Record<string, string> = {
    live: "border-success/25 bg-success-tint text-success",
    degraded: "border-warning/25 bg-warning-tint text-warning",
    deterministic: "border-warning/25 bg-warning-tint text-warning",
  };
  const labels: Record<string, string> = {
    live: "Live models",
    degraded: "Degraded",
    deterministic: "Templates only",
  };

  const explanation =
    health.mode === "live"
      ? `All model roles reachable (${health.healthy.join(", ")})`
      : `${broken.join(" · ")} — results come from grounded templates until this is fixed.`;

  return (
    <Tooltip label={explanation}>
      <span
        data-testid="mode-badge"
        data-mode={health.mode}
        tabIndex={0}
        className={`inline-flex items-center gap-1.5 rounded-[8px] border px-2 py-0.5 text-xs font-medium ${styles[health.mode] ?? styles.degraded}`}
      >
        <span aria-hidden>{health.mode === "live" ? "●" : "◐"}</span>
        {labels[health.mode] ?? health.mode}
      </span>
    </Tooltip>
  );
}
