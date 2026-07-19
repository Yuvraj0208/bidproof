// The confidence contract (US-13). These thresholds mirror the backend's
// apps/api/app/confidence.py exactly — one contract, two renderers.
export const GREEN_MIN = 0.7;
export const YELLOW_MIN = 0.4;

export type Band = "green" | "yellow" | "red";

export function bandFromConfidence(confidence: number): Band {
  if (confidence >= GREEN_MIN) return "green";
  if (confidence >= YELLOW_MIN) return "yellow";
  return "red";
}
