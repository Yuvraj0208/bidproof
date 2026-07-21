// The export blocker (US-10): export refuses while any mandatory clause is
// unaddressed or any claim is contradicted. The blockers are shown plainly,
// and an override requires a name and a written reason — which is logged.
import { useState } from "react";
import type { ExportBlocker } from "../api";

export function ExportBar({
  blockers,
  onExport,
  onOverride,
  busy,
}: {
  blockers: ExportBlocker[] | null;
  onExport: () => void;
  onOverride: (name: string, reason: string) => void;
  busy: boolean;
}) {
  const [name, setName] = useState("");
  const [reason, setReason] = useState("");
  const blocked = blockers != null && blockers.length > 0;

  return (
    <div className="rounded-lg border bg-white p-4">
      <div className="flex items-center gap-3">
        <span className="text-sm font-semibold text-slate-800">Export</span>
        <span
          data-testid="export-status"
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${blocked ? "bg-red-100 text-red-800" : "bg-emerald-100 text-emerald-800"}`}
        >
          {blockers == null
            ? "check readiness"
            : blocked
              ? `refused — ${blockers.length} blocker(s)`
              : "ready to export"}
        </span>
        <button
          data-testid="export-button"
          onClick={onExport}
          disabled={busy || blocked}
          className="ml-auto rounded bg-indigo-600 px-3 py-1 text-sm font-medium text-white disabled:opacity-40"
          title={blocked ? "resolve the blockers or override below" : undefined}
        >
          {busy ? "Working…" : "Export .docx"}
        </button>
      </div>

      {blocked && (
        <>
          <ul className="mt-3 space-y-1" data-testid="blocker-list">
            {blockers!.map((b, i) => (
              <li key={i} className="flex items-start gap-2 text-xs">
                <span className="shrink-0 rounded bg-red-100 px-1.5 text-red-700">
                  {b.type.replace(/_/g, " ")}
                </span>
                <span className="text-slate-600">{b.message}</span>
              </li>
            ))}
          </ul>

          <div className="mt-3 space-y-2 rounded border border-amber-200 bg-amber-50 p-3">
            <p className="text-xs font-medium text-amber-900">
              Override — exports anyway, and is logged with your name and reason.
            </p>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Your name"
              className="w-full rounded border px-2 py-1 text-sm"
            />
            <input
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Written reason (required)"
              className="w-full rounded border px-2 py-1 text-sm"
            />
            <button
              data-testid="override-button"
              disabled={busy || name.trim().length < 2 || reason.trim().length < 5}
              onClick={() => onOverride(name.trim(), reason.trim())}
              className="rounded border px-3 py-1 text-sm text-slate-700 disabled:opacity-40"
            >
              Override &amp; export
            </button>
          </div>
        </>
      )}
    </div>
  );
}
