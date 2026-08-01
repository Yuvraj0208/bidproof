// DataTable — the workhorse behind the compliance matrix and every queue.
//
// Priya lives in these tables, so: the header stays put while she scrolls, the
// columns sort, rows highlight under the cursor AND under the keyboard, and she
// can switch to compact density when she wants more rows on a projector
// (SPEC §17: dense, enterprise-grade, keyboard-navigable review queues).
import { useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

export interface Column<Row> {
  key: string;
  header: string;
  /** Cell renderer. Defaults to String(row[key]). */
  render?: (row: Row) => ReactNode;
  /** Value used for sorting; omit to make the column unsortable. */
  sortValue?: (row: Row) => string | number;
  align?: "left" | "right";
  width?: string;
  /** Money/date/count columns get tabular figures. */
  numeric?: boolean;
}

export function DataTable<Row>({
  columns,
  rows,
  rowKey,
  onRowActivate,
  empty,
  caption,
  density: densityProp,
  rowTestId = "data-row",
}: {
  columns: Column<Row>[];
  rows: Row[];
  rowKey: (row: Row) => string;
  /** Enter/Space on a focused row, or a click, activates it. */
  onRowActivate?: (row: Row) => void;
  empty?: ReactNode;
  caption?: string;
  density?: "comfortable" | "compact";
  /** Screens keep their own row hook (e.g. "matrix-row") for their tests. */
  rowTestId?: string;
}) {
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 } | null>(null);
  const [density, setDensity] = useState<"comfortable" | "compact">(
    densityProp ?? "comfortable",
  );
  const [focused, setFocused] = useState(0);
  const bodyRef = useRef<HTMLTableSectionElement>(null);

  const sorted = useMemo(() => {
    if (!sort) return rows;
    const column = columns.find((c) => c.key === sort.key);
    if (!column?.sortValue) return rows;
    return [...rows].sort((a, b) => {
      const av = column.sortValue!(a);
      const bv = column.sortValue!(b);
      if (av === bv) return 0;
      return (av > bv ? 1 : -1) * sort.dir;
    });
  }, [rows, sort, columns]);

  const toggleSort = (key: string) =>
    setSort((current) =>
      current?.key === key
        ? { key, dir: current.dir === 1 ? -1 : 1 }
        : { key, dir: 1 },
    );

  // Roving focus: ↑/↓ move between rows, Enter/Space activates.
  const onKeyDown = (event: React.KeyboardEvent<HTMLTableSectionElement>) => {
    if (!sorted.length) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const next = Math.min(
        sorted.length - 1,
        Math.max(0, focused + (event.key === "ArrowDown" ? 1 : -1)),
      );
      setFocused(next);
      const el = bodyRef.current?.querySelectorAll("tr")[next] as HTMLElement;
      el?.focus();
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onRowActivate?.(sorted[focused]);
    }
  };

  if (!rows.length && empty) return <>{empty}</>;

  const cellPad = density === "compact" ? "px-3 py-1.5" : "px-3 py-2.5";

  return (
    <div className="overflow-hidden rounded-[12px] border border-hairline bg-white shadow-card">
      <div className="flex items-center justify-between border-b border-hairline px-3 py-2">
        <span className="text-xs text-ink-subtle">
          {caption ?? `${rows.length} rows`}
        </span>
        <button
          data-testid="density-toggle"
          onClick={() =>
            setDensity((d) => (d === "compact" ? "comfortable" : "compact"))
          }
          className="rounded-[8px] border border-hairline px-2 py-0.5 text-xs text-ink-muted transition-colors duration-150 hover:bg-indigo-tint"
          title="Toggle row density"
        >
          {density === "compact" ? "Comfortable" : "Compact"}
        </button>
      </div>

      <div className="max-h-[70vh] overflow-auto">
        <table className="w-full border-collapse text-left text-sm">
          <thead className="sticky top-0 z-10 bg-surface/95 backdrop-blur">
            <tr>
              {columns.map((column) => {
                const active = sort?.key === column.key;
                return (
                  <th
                    key={column.key}
                    scope="col"
                    style={column.width ? { width: column.width } : undefined}
                    className={`${cellPad} border-b border-hairline text-xs font-semibold uppercase tracking-wide text-ink-subtle ${
                      column.align === "right" ? "text-right" : ""
                    }`}
                  >
                    {column.sortValue ? (
                      <button
                        onClick={() => toggleSort(column.key)}
                        aria-sort={
                          active
                            ? sort!.dir === 1
                              ? "ascending"
                              : "descending"
                            : "none"
                        }
                        className="inline-flex items-center gap-1 transition-colors duration-150 hover:text-ink"
                      >
                        {column.header}
                        <span aria-hidden className={active ? "" : "opacity-30"}>
                          {active && sort!.dir === -1 ? "▾" : "▴"}
                        </span>
                      </button>
                    ) : (
                      column.header
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody ref={bodyRef} onKeyDown={onKeyDown}>
            {sorted.map((row, index) => (
              <tr
                key={rowKey(row)}
                data-testid={rowTestId}
                tabIndex={index === focused ? 0 : -1}
                onFocus={() => setFocused(index)}
                onClick={() => onRowActivate?.(row)}
                // `group` lets a cell react to the whole row being hovered —
                // the Compliance Matrix uses it so the proof affordance
                // brightens wherever on the row you point.
                className={`group border-b border-hairline/70 transition-colors duration-150 last:border-0 ${
                  index % 2 ? "bg-surface/40" : "bg-white"
                } ${onRowActivate ? "cursor-pointer" : ""} hover:bg-indigo-tint focus:bg-indigo-tint focus:outline-none`}
              >
                {columns.map((column) => (
                  <td
                    key={column.key}
                    {...(column.numeric ? { "data-numeric": true } : {})}
                    className={`${cellPad} align-top text-ink ${
                      column.align === "right" ? "text-right" : ""
                    }`}
                  >
                    {column.render
                      ? column.render(row)
                      : String((row as Record<string, unknown>)[column.key] ?? "")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
