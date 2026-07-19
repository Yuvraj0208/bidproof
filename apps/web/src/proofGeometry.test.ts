// US-04: clicking a rule must highlight the RIGHT box — the geometry that
// places the overlay is deterministic and verified here.
import { describe, expect, it } from "vitest";
import { highlightRect } from "./proofGeometry";

describe("highlightRect", () => {
  it("maps a bbox to overlay pixels at scale 1 with padding", () => {
    const rect = highlightRect({ x0: 72, y0: 122, x1: 224, y1: 130 }, 1, 3);
    expect(rect).toEqual({ left: 69, top: 119, width: 158, height: 14 });
  });

  it("scales linearly with the viewport", () => {
    const rect = highlightRect({ x0: 100, y0: 200, x1: 300, y1: 240 }, 1.5, 0);
    expect(rect).toEqual({ left: 150, top: 300, width: 300, height: 60 });
  });

  it("keeps width and height positive for any valid bbox", () => {
    const rect = highlightRect({ x0: 10, y0: 10, x1: 11, y1: 11 }, 2, 3);
    expect(rect.width).toBeGreaterThan(0);
    expect(rect.height).toBeGreaterThan(0);
  });
});
