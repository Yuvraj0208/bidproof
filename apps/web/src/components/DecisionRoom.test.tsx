// US-06: EV terms rendered in rupees, sign-off gated on a named human,
// override gated on a written reason.
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DecisionRoom, type DecisionData } from "./DecisionRoom";

const DECISION: DecisionData = {
  recommendation: "go",
  ev_inr: 1155000,
  terms: [
    { key: "expected_profit", label: "Expected profit",
      formula: "P(win) 30% × margin 10% × value ₹500.00 lakh", value_inr: 1500000 },
    { key: "bid_effort", label: "Cost of bidding (effort)",
      formula: "12 man-days × ₹15,000/day", value_inr: -180000 },
  ],
  gate_failed: [],
  confidence: 0.9,
  band: "green",
  reason: "EV positive",
  status: "pending_signoff",
  signed_off_by: null,
};

describe("DecisionRoom", () => {
  it("shows the EV maths term by term in rupees", () => {
    render(<DecisionRoom decision={DECISION} risks={[]}
                         onSignOff={() => {}} onOverride={() => {}} />);
    expect(screen.getByTestId("recommendation")).toHaveTextContent("go");
    const terms = screen.getByTestId("ev-terms");
    expect(terms).toHaveTextContent("₹15.00 lakh");
    expect(terms).toHaveTextContent("12 man-days × ₹15,000/day");
    expect(terms).toHaveTextContent("−₹1.80 lakh");
    expect(terms).toHaveTextContent("₹11.55 lakh");
  });

  it("disables sign-off until a human is named", () => {
    const onSignOff = vi.fn();
    render(<DecisionRoom decision={DECISION} risks={[]}
                         onSignOff={onSignOff} onOverride={() => {}} />);
    const button = screen.getByTestId("signoff-button");
    expect(button).toBeDisabled();

    fireEvent.change(screen.getByPlaceholderText("Your name"),
                     { target: { value: "Priya N" } });
    expect(button).toBeEnabled();
    fireEvent.click(button);
    expect(onSignOff).toHaveBeenCalledWith("Priya N");
  });

  it("disables override until a reason is written", () => {
    render(<DecisionRoom decision={DECISION} risks={[]}
                         onSignOff={() => {}} onOverride={() => {}} />);
    fireEvent.change(screen.getByPlaceholderText("Your name"),
                     { target: { value: "Bid Head" } });
    const override = screen.getByTestId("override-button");
    expect(override).toBeDisabled();
    fireEvent.change(
      screen.getByPlaceholderText("Override reason (required, logged)"),
      { target: { value: "strategic conflict" } },
    );
    expect(override).toBeEnabled();
  });

  it("shows the hard gate when mandatory eligibility failed", () => {
    render(<DecisionRoom
      decision={{ ...DECISION, recommendation: "no_go", ev_inr: null,
                  terms: [], gate_failed: [{ key: "min_turnover" }] }}
      risks={[]} onSignOff={() => {}} onOverride={() => {}} />);
    expect(screen.getByText(/Hard gate/)).toHaveTextContent("min_turnover");
  });
});
