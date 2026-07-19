// Click-to-proof geometry (US-04). Element bboxes are stored in PDF points
// with a top-left origin (the parser's coordinate contract); a pdf.js
// viewport at `scale` multiplies points by that scale — so the highlight
// overlay is a plain linear map. Deterministic, unit-tested.
export interface BBox {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export interface HighlightRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

export function highlightRect(bbox: BBox, scale: number, pad = 3): HighlightRect {
  return {
    left: bbox.x0 * scale - pad,
    top: bbox.y0 * scale - pad,
    width: (bbox.x1 - bbox.x0) * scale + 2 * pad,
    height: (bbox.y1 - bbox.y0) * scale + 2 * pad,
  };
}
