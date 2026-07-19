// US-13 acceptance tests: chip renders each band, hover reason present,
// band thresholds correct (mirroring the backend contract exactly).
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { bandFromConfidence } from "../confidence";
import { ConfidenceChip } from "./ConfidenceChip";

describe("ConfidenceChip", () => {
  it("renders the green band with dot and percentage", () => {
    render(<ConfidenceChip confidence={0.9} band="green" reason="all checks pass" />);
    const chip = screen.getByTitle("all checks pass");
    expect(chip).toHaveAttribute("data-band", "green");
    expect(chip).toHaveTextContent("90%");
    expect(screen.getByTestId("chip-dot")).toHaveClass("bg-emerald-500");
  });

  it("renders the yellow band", () => {
    render(<ConfidenceChip confidence={0.55} band="yellow" reason="partly known" />);
    expect(screen.getByTitle("partly known")).toHaveAttribute("data-band", "yellow");
    expect(screen.getByTestId("chip-dot")).toHaveClass("bg-amber-400");
  });

  it("renders the red band", () => {
    render(<ConfidenceChip confidence={0.1} band="red" reason="almost nothing known" />);
    expect(screen.getByTitle("almost nothing known")).toHaveAttribute(
      "data-band",
      "red",
    );
    expect(screen.getByTestId("chip-dot")).toHaveClass("bg-red-500");
  });

  it("exposes the why on hover via the title attribute", () => {
    render(
      <ConfidenceChip confidence={0.8} band="green" reason="category matched 100%" />,
    );
    expect(screen.getByTitle("category matched 100%")).toBeInTheDocument();
  });

  it("derives the band from confidence when none is given", () => {
    render(<ConfidenceChip confidence={0.75} reason="derived" />);
    expect(screen.getByTitle("derived")).toHaveAttribute("data-band", "green");
  });
});

describe("bandFromConfidence — the contract thresholds", () => {
  it("matches the backend thresholds exactly", () => {
    expect(bandFromConfidence(1.0)).toBe("green");
    expect(bandFromConfidence(0.7)).toBe("green");
    expect(bandFromConfidence(0.69)).toBe("yellow");
    expect(bandFromConfidence(0.4)).toBe("yellow");
    expect(bandFromConfidence(0.39)).toBe("red");
    expect(bandFromConfidence(0)).toBe("red");
  });
});
