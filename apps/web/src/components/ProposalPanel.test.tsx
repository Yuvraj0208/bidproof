// US-09 + US-11: sections render with claim badges, three scores, and
// individual approval that is blocked while a flag is open.
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProposalPanel } from "./ProposalPanel";
import type { Proposal, ProposalSection } from "../api";

const clean: ProposalSection = {
  id: "s-1",
  section_tag: "company_profile",
  position: 0,
  content: "Annual turnover of ₹150.00 crore in FY 2024-25. [F:aaaaaaaa]",
  claims: [
    { text: "Annual turnover of ₹150.00 crore. [F:aaaaaaaa]",
      source_tag: "[F:aaaaaaaa]", status: "verified" },
  ],
  verified_pct: 100,
  requirements_covered_pct: 40,
  style_match_pct: 25,
  dropped_untagged: 1,
  approved: false,
  approved_by: null,
  open_flags: [],
};

const flagged: ProposalSection = {
  ...clean,
  id: "s-2",
  section_tag: "technical_approach",
  claims: [
    { text: "Turnover ₹777 crore. [F:aaaaaaaa]", source_tag: "[F:aaaaaaaa]",
      status: "contradicted" },
  ],
  open_flags: ["contradicted"],
};

const PROPOSAL: Proposal = {
  id: "p-1",
  tender_id: "t-1",
  status: "draft",
  format_source: "default_template",
  duration_ms: 42,
  sections: [clean, flagged],
};

describe("ProposalPanel", () => {
  it("shows the three per-section scores", () => {
    render(<ProposalPanel proposal={PROPOSAL} onGenerate={() => {}}
                          onApprove={() => {}} busy={false} />);
    const section = screen.getAllByTestId("proposal-section")[0];
    expect(section).toHaveTextContent("verified 100%");
    expect(section).toHaveTextContent("reqs 40%");
    expect(section).toHaveTextContent("style 25%");
  });

  it("approves a section individually, gated on a name — no approve-all", () => {
    const onApprove = vi.fn();
    render(<ProposalPanel proposal={PROPOSAL} onGenerate={() => {}}
                          onApprove={onApprove} busy={false} />);
    // one approve button per unapproved section — each signed off on its own
    const buttons = screen.getAllByTestId("approve-button");
    expect(buttons).toHaveLength(2);
    expect(buttons[0]).toBeDisabled();        // no name yet

    fireEvent.change(screen.getByPlaceholderText(/Your name/),
                     { target: { value: "Priya N" } });
    const clean = buttons[0];                 // the clean section (no flags)
    expect(clean).toBeEnabled();
    fireEvent.click(clean);
    expect(onApprove).toHaveBeenCalledWith("s-1", "Priya N");

    // there is no single control that approves everything at once
    expect(screen.queryByText(/approve all/i)).toBeNull();
  });

  it("blocks approval of a section with an open flag even with a name", () => {
    render(<ProposalPanel proposal={PROPOSAL} onGenerate={() => {}}
                          onApprove={() => {}} busy={false} />);
    fireEvent.change(screen.getByPlaceholderText(/Your name/),
                     { target: { value: "Priya N" } });
    // the flagged section shows its warning and its approve button stays disabled
    expect(screen.getByTestId("open-flags")).toHaveTextContent("open flag");
    const flaggedButton = screen.getAllByTestId("approve-button")[1];
    expect(flaggedButton).toBeDisabled();
  });

  it("tracks approval progress and readiness", () => {
    const allApproved: Proposal = {
      ...PROPOSAL,
      sections: PROPOSAL.sections.map((s) => ({
        ...s, approved: true, approved_by: "Priya N", open_flags: [],
      })),
    };
    render(<ProposalPanel proposal={allApproved} onGenerate={() => {}}
                          onApprove={() => {}} busy={false} />);
    expect(screen.getByTestId("approval-progress")).toHaveTextContent(
      "all sections approved",
    );
  });

  it("invites drafting when there is no proposal", () => {
    render(<ProposalPanel proposal={null} onGenerate={() => {}}
                          onApprove={() => {}} busy={false} />);
    expect(screen.getByText(/once the decision is GO/)).toBeInTheDocument();
  });
});
