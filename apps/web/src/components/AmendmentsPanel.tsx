// Amendment alerts (US-07): each corrigendum names exactly what changed,
// which rules broke, and how the EV moved. Upload a corrigendum to run the
// watcher.
import { useRef } from "react";
import type { Amendment } from "../api";

const lakh = (value: number | null) =>
  value == null ? "unknown" : `₹${(value / 1e5).toFixed(2)}L`;

export function AmendmentsPanel({
  amendments,
  onAmend,
  busy,
}: {
  amendments: Amendment[];
  onAmend: (file: File) => void;
  busy: boolean;
}) {
  const fileRef = useRef<HTMLInputElement>(null);

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-6">
      <div className="flex items-center gap-3">
        <h2 className="text-sm font-semibold text-slate-800">Amendments</h2>
        <input
          ref={fileRef}
          type="file"
          accept="application/pdf"
          data-testid="corrigendum-input"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) onAmend(file);
            e.target.value = "";
          }}
        />
        <button
          onClick={() => fileRef.current?.click()}
          disabled={busy}
          className="ml-auto rounded border px-2 py-1 text-sm text-slate-600 hover:bg-slate-50 disabled:opacity-50"
        >
          {busy ? "Applying…" : "Upload corrigendum"}
        </button>
      </div>

      {amendments.length === 0 && (
        <p className="text-sm text-slate-500">
          No amendments yet. Upload a corrigendum to diff it against this tender.
        </p>
      )}

      {amendments.map((a) => {
        const flipped =
          a.ev_before_inr != null &&
          a.ev_after_inr != null &&
          Math.sign(a.ev_before_inr) !== Math.sign(a.ev_after_inr);
        return (
          <article
            key={a.id}
            data-testid="amendment-alert"
            className="rounded-lg border border-amber-200 bg-amber-50 p-4"
          >
            <p className="text-sm font-medium text-amber-900">{a.message}</p>
            <table className="mt-2 w-full text-xs" data-testid="amendment-changes">
              <tbody>
                {a.changes.map((c) => (
                  <tr key={c.key} className="border-b border-amber-100">
                    <td className="py-1 font-mono text-slate-700">{c.key}</td>
                    <td className="py-1 text-slate-500">
                      {c.old_value ?? "—"} → {c.new_value ?? "—"}
                      {c.page ? ` (p.${c.page})` : ""}
                    </td>
                    <td className="py-1 text-right">
                      {a.rules_broken.includes(c.key) && (
                        <span className="rounded bg-red-100 px-1.5 text-red-700">
                          broke
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div
              className="mt-2 text-sm font-medium"
              data-testid="amendment-ev"
            >
              EV {lakh(a.ev_before_inr)} →{" "}
              <span className={flipped ? "text-red-700" : "text-slate-900"}>
                {lakh(a.ev_after_inr)}
              </span>
            </div>
          </article>
        );
      })}
    </div>
  );
}
