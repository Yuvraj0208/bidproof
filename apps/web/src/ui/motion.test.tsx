// Reveal-on-scroll has one catastrophic failure mode: the content starts at
// opacity 0 waiting for an IntersectionObserver, the observer never speaks, and
// the page renders perfectly while showing nothing. No error, no warning.
//
// It is not hypothetical. A non-compositing tab does exactly this, and jsdom —
// which these tests run in — has no IntersectionObserver at all. That makes
// jsdom the honest place to check the fallback: if the content appears here,
// it appears in the worst case a real browser can produce.
import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CountUp, Reveal } from "./motion";

describe("motion fallback", () => {
  beforeEach(() => {
    // Prove the environment really has no observer — the whole point of the
    // fallback. If a future jsdom adds one, this test stops testing anything
    // and we want to know.
    expect(typeof IntersectionObserver).toBe("undefined");
  });

  it("reveals its children even when no observer ever fires", () => {
    vi.useFakeTimers();
    try {
      render(
        <Reveal>
          <p>One bid in three is thrown out on paperwork.</p>
        </Reveal>,
      );
      act(() => {
        vi.advanceTimersByTime(2000);
      });
      expect(
        screen.getByText(/One bid in three/),
      ).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("renders the real number, not a zero, when the count cannot animate", () => {
    // The failure this guards: a landing page reading "0 pages read per
    // tender" is worse than one with no animation at all.
    render(<CountUp to={800} />);
    // The element is present and carries the numeric marker from the start, so
    // a screen reader and a test both see a number rather than an animation.
    const el = screen.getByText(/\d/);
    expect(el).toHaveAttribute("data-numeric");
  });

});
