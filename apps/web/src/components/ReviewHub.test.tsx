// R3: one place that answers "what is waiting for me?" — every SPEC §7
// checkpoint, numbered, with the control that clears it.
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ReviewHub, pendingReviews } from "./ReviewHub";

const CLEAR = {
  rulesNeedingHuman: 0,
  verdictsNeedingHuman: 0,
  decisionStatus: "signed_off",
  proposalSections: [{ approved: true }],
  exportBlockers: 0,
  checklistRequired: 2,
  checklistTicked: 2,
};

describe("pendingReviews", () => {
  it("is empty when every checkpoint is clear", () => {
    expect(pendingReviews(CLEAR)).toEqual([]);
  });

  it("collects each checkpoint and orders them by number", () => {
    const items = pendingReviews({
      checkpoint0: "queued",
      rulesNeedingHuman: 3,
      verdictsNeedingHuman: 5,
      decisionStatus: "pending_signoff",
      decisionRecommendation: "go",
      proposalSections: [{ approved: false }, { approved: true }],
      exportBlockers: 2,
      checklistRequired: 4,
      checklistTicked: 1,
    });
    expect(items.map((i) => i.checkpoint)).toEqual([0, 2, 3, 4, 5, 6, 6]);
    expect(items.find((i) => i.checkpoint === 3)?.count).toBe(5);
    expect(items.find((i) => i.checkpoint === 5)?.count).toBe(1);
  });

  it("marks the checkpoints that block submission", () => {
    const items = pendingReviews({ ...CLEAR, verdictsNeedingHuman: 1 });
    expect(items[0].blocking).toBe(true);
  });

  it("names the recommendation in the sign-off ask", () => {
    const items = pendingReviews({
      ...CLEAR,
      decisionStatus: "pending_signoff",
      decisionRecommendation: "no_go",
    });
    expect(items[0].title).toContain("NO_GO");
  });

  it("does not ask for a checklist that does not exist yet", () => {
    expect(pendingReviews({ ...CLEAR, checklistRequired: 0, checklistTicked: 0 })).toEqual([]);
  });
});

describe("ReviewHub", () => {
  it("teaches rather than looking broken when nothing is pending", () => {
    render(<ReviewHub items={[]} onGoTo={() => {}} />);
    expect(screen.getByTestId("empty-state")).toHaveTextContent("Nothing is waiting");
  });

  it("routes the human to the control that clears the item", () => {
    const onGoTo = vi.fn();
    render(
      <ReviewHub
        items={pendingReviews({ ...CLEAR, verdictsNeedingHuman: 2 })}
        onGoTo={onGoTo}
      />,
    );
    expect(screen.getAllByTestId("review-item")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: /Open matrix/ }));
    expect(onGoTo).toHaveBeenCalledWith("matrix");
  });
});
