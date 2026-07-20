// US-07: the alert names what changed, which rules broke, and the new EV.
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AmendmentsPanel } from "./AmendmentsPanel";
import type { Amendment } from "../api";

const AMENDMENT: Amendment = {
  id: "a-1",
  document_id: "doc-corr",
  message:
    "delivery_days 90→30 (corrigendum, p.1); pbg_percent 5→10 (corrigendum, p.1). Breaks delivery_days. EV ₹11.55L → ₹10.05L.",
  changes: [
    { key: "delivery_days", family: "commercial", change: "revised",
      old_value: "90", new_value: "30", page: 1 },
    { key: "pbg_percent", family: "commercial", change: "revised",
      old_value: "5", new_value: "10", page: 1 },
  ],
  rules_affected: ["delivery_days", "pbg_percent"],
  rules_broken: ["delivery_days"],
  ev_before_inr: 1155000,
  ev_after_inr: 1005000,
  created_at: "2026-07-20T10:00:00Z",
};

describe("AmendmentsPanel", () => {
  it("shows the alert message, the change rows, and the broken flag", () => {
    render(<AmendmentsPanel amendments={[AMENDMENT]} onAmend={() => {}} busy={false} />);
    expect(screen.getByTestId("amendment-alert")).toHaveTextContent(
      "delivery_days 90→30",
    );
    const changes = screen.getByTestId("amendment-changes");
    expect(changes).toHaveTextContent("90 → 30 (p.1)");
    expect(changes).toHaveTextContent("broke");
    expect(screen.getByTestId("amendment-ev")).toHaveTextContent(
      "EV ₹11.55L → ₹10.05L",
    );
  });

  it("uploads a corrigendum file", () => {
    const onAmend = vi.fn();
    render(<AmendmentsPanel amendments={[]} onAmend={onAmend} busy={false} />);
    const input = screen.getByTestId("corrigendum-input");
    const file = new File(["%PDF-1.4"], "corrigendum.pdf", { type: "application/pdf" });
    fireEvent.change(input, { target: { files: [file] } });
    expect(onAmend).toHaveBeenCalledWith(file);
  });

  it("shows the empty state when there are no amendments", () => {
    render(<AmendmentsPanel amendments={[]} onAmend={() => {}} busy={false} />);
    expect(screen.getByText(/No amendments yet/)).toBeInTheDocument();
  });
});
