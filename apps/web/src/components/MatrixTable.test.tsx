// US-05: every matrix row shows verdict + proof + confidence, and a
// NEEDS-HUMAN row is visibly queued. Row click drives click-to-proof.
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MatrixTable, type VerdictRow } from "./MatrixTable";

const ROW: VerdictRow = {
  id: "v-1",
  rule_id: "r-1",
  family: "eligibility",
  key: "min_turnover",
  requirement_text: "Minimum average annual turnover: Rs 5 crore",
  value: "Rs 5 crore",
  verdict: "complies",
  reason: "average turnover over 3 FY is ₹135.00 cr vs required ₹5.00 cr",
  confidence: 0.95,
  band: "green",
  arithmetic: true,
  document_id: "doc-1",
  page_no: 1,
  bbox: { x0: 73, y0: 188, x1: 369, y1: 198 },
  system_verdict: null,
  decided_by: null,
  decided_at: null,
  decided_reason: null,
};

const QUEUED: VerdictRow = {
  ...ROW,
  id: "v-2",
  key: "special_condition",
  verdict: "needs_human",
  reason: "no judge available — a human decides",
  confidence: 0.4,
  band: "red",
  arithmetic: false,
};

describe("MatrixTable", () => {
  it("renders every row with verdict, proof reference, and confidence chip", () => {
    render(<MatrixTable verdicts={[ROW, QUEUED]} onProof={() => {}} />);
    const rows = screen.getAllByTestId("matrix-row");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent("complies");
    expect(rows[0]).toHaveTextContent("p.1");
    expect(rows[0].querySelector('[data-band="green"]')).not.toBeNull();
  });

  it("marks a needs-human row as visibly queued", () => {
    render(<MatrixTable verdicts={[ROW, QUEUED]} onProof={() => {}} />);
    expect(screen.getByTestId("queued-badge")).toHaveTextContent(
      "queued for human",
    );
  });

  it("clicking a row fires click-to-proof with the row's page and bbox", () => {
    const onProof = vi.fn();
    render(<MatrixTable verdicts={[ROW]} onProof={onProof} />);
    fireEvent.click(screen.getByTestId("matrix-row"));
    expect(onProof).toHaveBeenCalledWith({
      page_no: 1,
      bbox: ROW.bbox,
      document_id: "doc-1",
    });
  });

  // The bug this closes: the matrix told you 10 verdicts were yours to settle
  // and gave you no way to settle them.
  it("offers a way to decide a needs-human row", () => {
    const onDecide = vi.fn();
    render(
      <MatrixTable verdicts={[ROW, QUEUED]} onProof={() => {}} onDecide={onDecide} />,
    );
    fireEvent.click(screen.getByTestId("decide-verdict"));
    expect(onDecide).toHaveBeenCalledWith(QUEUED);
  });

  it("offers no decision control on a row the system already settled", () => {
    render(<MatrixTable verdicts={[ROW]} onProof={() => {}} onDecide={() => {}} />);
    expect(screen.queryByTestId("decide-verdict")).toBeNull();
  });

  it("deciding does not also fire click-to-proof", () => {
    const onProof = vi.fn();
    render(
      <MatrixTable verdicts={[QUEUED]} onProof={onProof} onDecide={() => {}} />,
    );
    fireEvent.click(screen.getByTestId("decide-verdict"));
    expect(onProof).not.toHaveBeenCalled();
  });

  it("shows a human answer as a human answer, with what the system had said", () => {
    const decided: VerdictRow = {
      ...QUEUED,
      verdict: "complies",
      system_verdict: "needs_human",
      decided_by: "Yuvraj",
      decided_at: "2026-07-26T12:00:00Z",
      decided_reason: "6 years on comparable surveys",
      confidence: 1,
      band: "green",
    };
    render(<MatrixTable verdicts={[decided]} onProof={() => {}} onDecide={() => {}} />);
    const badge = screen.getByTestId("decided-badge");
    expect(badge).toHaveTextContent("you decided");
    expect(badge).toHaveTextContent("needs_human");
    // It is settled, so it must no longer be queued or offer a Decide button.
    expect(screen.queryByTestId("queued-badge")).toBeNull();
    expect(screen.queryByTestId("decide-verdict")).toBeNull();
  });
});
