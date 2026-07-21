// US-14: the leaderboard renders a row per model with the metric columns and
// names the winner.
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ModelLab } from "./ModelLab";
import type { ModelLabResult } from "../api";

const RESULT: ModelLabResult = {
  role: "extraction",
  gold_tenders: 25,
  simulated: true,
  leaderboard: [
    { model: "claude (paid)", kind: "paid", f1_overall: 0.98, f1_eligibility: 0.99,
      exact_numbers: 0.99, hallucination_rate: 0.01, citation_complete: 0.99,
      speed_ms: 1000, cost_per_tender_inr: 7.0, simulated: true },
    { model: "qwen3-30b (open)", kind: "open", f1_overall: 0.95, f1_eligibility: 0.94,
      exact_numbers: 0.95, hallucination_rate: 0.06, citation_complete: 0.9,
      speed_ms: 900, cost_per_tender_inr: 0.8, simulated: true },
  ],
};

describe("ModelLab", () => {
  it("renders a row per model with the metric columns", () => {
    render(<ModelLab result={RESULT} onRun={() => {}} busy={false} />);
    expect(screen.getAllByTestId("lab-row")).toHaveLength(2);
    const table = screen.getByTestId("leaderboard");
    expect(table).toHaveTextContent("claude (paid)");
    expect(table).toHaveTextContent("qwen3-30b (open)");
    expect(table).toHaveTextContent("₹0.8");
  });

  it("names the winner by F1", () => {
    render(<ModelLab result={RESULT} onRun={() => {}} busy={false} />);
    expect(screen.getByText(/Winner by F1/)).toHaveTextContent("claude (paid)");
  });

  it("runs the leaderboard on demand", () => {
    const onRun = vi.fn();
    render(<ModelLab result={null} onRun={onRun} busy={false} />);
    fireEvent.click(screen.getByText("Run leaderboard"));
    expect(onRun).toHaveBeenCalled();
  });
});
