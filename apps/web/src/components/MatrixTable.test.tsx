// US-05: every matrix row shows verdict + proof + confidence, and a
// NEEDS-HUMAN row is visibly queued. Row click drives click-to-proof.
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MatrixTable, type VerdictRow } from "./MatrixTable";

const ROW: VerdictRow = {
  id: "v-1",
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
});
