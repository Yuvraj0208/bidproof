// Design-system contracts. These guard the promises the SPEC makes about the
// UI: countdowns turn red when urgent, verdicts never rely on colour alone,
// money reads in lakh/crore, and the review queues are keyboard-navigable.
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CountdownChip, RiskTag, VerdictBadge, daysUntil, formatInr } from "./chips";
import { DataTable } from "./DataTable";
import { EmptyState, StatCallout } from "./primitives";

const DAY = 86_400_000;
const NOW = new Date("2026-07-25T12:00:00Z");
const inDays = (d: number) => new Date(NOW.getTime() + d * DAY).toISOString();

describe("CountdownChip", () => {
  it("is calm when the deadline is far away", () => {
    render(<CountdownChip closingAt={inDays(30)} now={NOW} />);
    const chip = screen.getByTestId("countdown-chip");
    expect(chip).toHaveTextContent("30d left");
    expect(chip.className).not.toMatch(/danger|warning/);
  });

  it("warns in amber under 7 days", () => {
    render(<CountdownChip closingAt={inDays(5)} now={NOW} />);
    expect(screen.getByTestId("countdown-chip").className).toContain("warning");
  });

  it("turns red under 3 days", () => {
    render(<CountdownChip closingAt={inDays(2)} now={NOW} />);
    expect(screen.getByTestId("countdown-chip").className).toContain("danger");
  });

  it("pulses under 24 hours and counts in hours", () => {
    render(<CountdownChip closingAt={inDays(0.25)} now={NOW} />);
    const chip = screen.getByTestId("countdown-chip");
    expect(chip).toHaveAttribute("data-urgent", "true");
    expect(chip).toHaveTextContent("6h left");
  });

  it("says Closed rather than showing a negative countdown", () => {
    render(<CountdownChip closingAt={inDays(-2)} now={NOW} />);
    expect(screen.getByTestId("countdown-chip")).toHaveTextContent("Closed");
  });

  it("handles a missing or unparseable deadline", () => {
    expect(daysUntil(null)).toBeNull();
    expect(daysUntil("not-a-date")).toBeNull();
    render(<CountdownChip closingAt={null} />);
    expect(screen.getByTestId("countdown-chip")).toHaveTextContent("No deadline");
  });
});

describe("VerdictBadge", () => {
  it("carries a word and a glyph, so colour is never the only signal", () => {
    render(<VerdictBadge verdict="complies" />);
    const badge = screen.getByTestId("verdict-badge");
    expect(badge).toHaveTextContent("Complies");
    expect(badge.textContent).toMatch(/[✓◐✕?–]/);
  });

  it("renders an unknown verdict readably rather than blank", () => {
    render(<VerdictBadge verdict="some_new_state" />);
    expect(screen.getByTestId("verdict-badge")).toHaveTextContent("some new state");
  });
});

describe("formatInr", () => {
  it("reads in lakh and crore the way Indian finance does", () => {
    expect(formatInr(15000000)).toBe("₹1.50 crore");
    expect(formatInr(250000)).toBe("₹2.50 lakh");
    expect(formatInr(4500)).toBe("₹4,500");
  });

  it("marks negatives and copes with nothing", () => {
    expect(formatInr(-180000)).toBe("−₹1.80 lakh");
    expect(formatInr(null)).toBe("—");
  });
});

describe("RiskTag", () => {
  it("shows the rupee impact alongside the risk", () => {
    render(<RiskTag label="Liquidated damages" impactInr={450000} severity="high" />);
    const tag = screen.getByTestId("risk-tag");
    expect(tag).toHaveTextContent("Liquidated damages");
    expect(tag).toHaveTextContent("₹4.50 lakh");
  });
});

describe("StatCallout", () => {
  it("marks the number as tabular so figures do not jitter", () => {
    render(<StatCallout label="Expected value" value="₹11.55 lakh" hint="EV" />);
    const callout = screen.getByTestId("stat-callout");
    expect(callout.querySelector("[data-numeric]")).not.toBeNull();
  });
});

describe("EmptyState", () => {
  it("teaches and offers the action that would fill it", () => {
    render(
      <EmptyState
        title="No tenders yet"
        body="Connect a portal or upload one."
        action={<button>Upload</button>}
      />,
    );
    expect(screen.getByTestId("empty-state")).toHaveTextContent("Connect a portal");
    expect(screen.getByRole("button", { name: "Upload" })).toBeInTheDocument();
  });
});

interface R { id: string; name: string; n: number }
const ROWS: R[] = [
  { id: "b", name: "Beta", n: 2 },
  { id: "a", name: "Alpha", n: 30 },
  { id: "c", name: "Gamma", n: 1 },
];

function table(onRowActivate?: (r: R) => void) {
  return render(
    <DataTable<R>
      rows={ROWS}
      rowKey={(r) => r.id}
      onRowActivate={onRowActivate}
      columns={[
        { key: "name", header: "Name", sortValue: (r) => r.name },
        { key: "n", header: "Count", numeric: true, align: "right", sortValue: (r) => r.n },
      ]}
    />,
  );
}

describe("DataTable", () => {
  it("sorts by a column and reverses on a second click", () => {
    table();
    const header = screen.getByRole("button", { name: /Name/ });
    fireEvent.click(header);
    expect(screen.getAllByTestId("data-row")[0]).toHaveTextContent("Alpha");
    fireEvent.click(header);
    expect(screen.getAllByTestId("data-row")[0]).toHaveTextContent("Gamma");
  });

  it("sorts numerically, not lexically", () => {
    table();
    fireEvent.click(screen.getByRole("button", { name: /Count/ }));
    const rows = screen.getAllByTestId("data-row");
    // 1, 2, 30 — a string sort would put 30 before 1.
    expect(rows[0]).toHaveTextContent("Gamma");
    expect(rows[2]).toHaveTextContent("Alpha");
  });

  it("is keyboard navigable: arrows move, Enter activates", () => {
    const onRowActivate = vi.fn();
    table(onRowActivate);
    const rows = screen.getAllByTestId("data-row");
    rows[0].focus();
    fireEvent.keyDown(rows[0], { key: "ArrowDown" });
    fireEvent.keyDown(rows[1], { key: "Enter" });
    expect(onRowActivate).toHaveBeenCalledWith(ROWS[1]);
  });

  it("switches density on demand", () => {
    table();
    const toggle = screen.getByTestId("density-toggle");
    expect(toggle).toHaveTextContent("Compact");
    fireEvent.click(toggle);
    expect(toggle).toHaveTextContent("Comfortable");
  });

  it("shows the empty state instead of an empty grid", () => {
    render(
      <DataTable<R>
        rows={[]}
        rowKey={(r) => r.id}
        columns={[{ key: "name", header: "Name" }]}
        empty={<EmptyState title="Nothing here" body="Run a check first." />}
      />,
    );
    expect(screen.getByTestId("empty-state")).toBeInTheDocument();
  });
});
