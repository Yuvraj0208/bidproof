// Submission checklist (US-18, Checkpoint 6): every required document, the
// system's format + signature check, and a human tick on each. Nothing is
// submit-ready until every required item is ticked.
import { useState } from "react";
import type { Checklist, ChecklistItem } from "../api";

export function ChecklistPanel({
  checklist,
  name,
  onName,
  onAttach,
  onTick,
  onGenerate,
}: {
  checklist: Checklist | null;
  name: string;
  onName: (name: string) => void;
  onAttach: (itemId: string, format: string, signed: boolean) => void;
  onTick: (itemId: string) => void;
  onGenerate: () => void;
}) {
  return (
    <div className="mx-auto max-w-2xl space-y-4 p-6">
      <div className="flex items-center gap-3">
        <h2 className="text-sm font-semibold text-slate-800">
          Submission checklist
        </h2>
        {checklist && (
          <span
            data-testid="submit-status"
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${checklist.submit_ready ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}`}
          >
            {checklist.submit_ready
              ? "submit-ready"
              : `${checklist.ticked_count}/${checklist.required_count} ticked`}
          </span>
        )}
        {!checklist && (
          <button
            onClick={onGenerate}
            className="ml-auto rounded border px-2 py-1 text-sm text-slate-600 hover:bg-slate-50"
          >
            Build checklist
          </button>
        )}
      </div>

      {checklist && (
        <input
          value={name}
          onChange={(e) => onName(e.target.value)}
          placeholder="Your name (to tick items)"
          className="w-full rounded border px-2 py-1 text-sm"
        />
      )}

      {checklist?.items.map((item) => (
        <ChecklistRow
          key={item.id}
          item={item}
          canTick={name.trim().length >= 2}
          onAttach={onAttach}
          onTick={onTick}
        />
      ))}
    </div>
  );
}

function ChecklistRow({
  item,
  canTick,
  onAttach,
  onTick,
}: {
  item: ChecklistItem;
  canTick: boolean;
  onAttach: (itemId: string, format: string, signed: boolean) => void;
  onTick: (itemId: string) => void;
}) {
  const [format, setFormat] = useState(item.required_format);
  const [signed, setSigned] = useState(false);

  return (
    <article
      data-testid="checklist-item"
      className={`rounded-lg border bg-white p-3 ${item.ticked ? "border-emerald-300" : ""}`}
    >
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-slate-800">{item.name}</span>
        <span className="text-[11px] text-slate-400">
          needs .{item.required_format}
          {item.signature_required ? " · signed" : ""}
        </span>
        <span
          data-testid="checks-status"
          className={`ml-auto rounded px-1.5 py-0.5 text-[11px] ${item.checks_pass ? "bg-emerald-100 text-emerald-800" : "bg-red-100 text-red-700"}`}
        >
          {item.checks_pass ? "checks pass" : (item.checks_reason ?? "no file")}
        </span>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
        <input
          value={format}
          onChange={(e) => setFormat(e.target.value)}
          className="w-20 rounded border px-1.5 py-0.5"
          aria-label={`format for ${item.name}`}
        />
        <label className="flex items-center gap-1 text-slate-600">
          <input
            type="checkbox"
            checked={signed}
            onChange={(e) => setSigned(e.target.checked)}
          />
          signed
        </label>
        <button
          data-testid="attach-button"
          onClick={() => onAttach(item.id, format, signed)}
          className="rounded border px-2 py-0.5 text-slate-600 hover:bg-slate-50"
        >
          Attach file
        </button>
        <div className="ml-auto">
          {item.ticked ? (
            <span
              data-testid="ticked-badge"
              className="rounded bg-emerald-100 px-2 py-0.5 font-medium text-emerald-800"
            >
              ✓ {item.ticked_by}
            </span>
          ) : (
            <button
              data-testid="tick-button"
              disabled={!canTick || !item.checks_pass}
              onClick={() => onTick(item.id)}
              className="rounded bg-indigo-600 px-2 py-0.5 font-medium text-white disabled:opacity-40"
            >
              Tick
            </button>
          )}
        </div>
      </div>
    </article>
  );
}
