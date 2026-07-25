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
        <h2 className="text-sm font-semibold text-ink">
          Submission checklist
        </h2>
        {checklist && (
          <span
            data-testid="submit-status"
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${checklist.submit_ready ? "bg-success-tint text-success" : "bg-warning-tint text-warning"}`}
          >
            {checklist.submit_ready
              ? "submit-ready"
              : `${checklist.ticked_count}/${checklist.required_count} ticked`}
          </span>
        )}
        {!checklist && (
          <button
            onClick={onGenerate}
            className="ml-auto rounded-[8px] border border-hairline px-2 py-1 text-sm text-ink-muted hover:bg-surface"
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
          className="w-full rounded-[8px] border border-hairline px-2 py-1 text-sm"
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
      className={`rounded-[12px] border bg-white p-3 ${item.ticked ? "border-success/40" : "border-hairline"}`}
    >
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-ink">{item.name}</span>
        <span className="text-[11px] text-ink-subtle">
          needs .{item.required_format}
          {item.signature_required ? " · signed" : ""}
        </span>
        <span
          data-testid="checks-status"
          className={`ml-auto rounded-[8px] px-1.5 py-0.5 text-[11px] ${item.checks_pass ? "bg-success-tint text-success" : "bg-danger-tint text-danger"}`}
        >
          {item.checks_pass ? "checks pass" : (item.checks_reason ?? "no file")}
        </span>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
        <input
          value={format}
          onChange={(e) => setFormat(e.target.value)}
          className="w-20 rounded-[8px] border border-hairline px-1.5 py-0.5"
          aria-label={`format for ${item.name}`}
        />
        <label className="flex items-center gap-1 text-ink-muted">
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
          className="rounded-[8px] border border-hairline px-2 py-0.5 text-ink-muted hover:bg-surface"
        >
          Attach file
        </button>
        <div className="ml-auto">
          {item.ticked ? (
            <span
              data-testid="ticked-badge"
              className="rounded-[8px] bg-success-tint px-2 py-0.5 font-medium text-success"
            >
              ✓ {item.ticked_by}
            </span>
          ) : (
            <button
              data-testid="tick-button"
              disabled={!canTick || !item.checks_pass}
              onClick={() => onTick(item.id)}
              className="rounded-[8px] bg-indigo px-2 py-0.5 font-medium text-white disabled:opacity-40"
            >
              Tick
            </button>
          )}
        </div>
      </div>
    </article>
  );
}
