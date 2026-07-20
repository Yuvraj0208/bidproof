// US-09: sections render with per-claim badges and the verified-% chip.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProposalPanel } from "./ProposalPanel";
import type { Proposal } from "../api";

const PROPOSAL: Proposal = {
  id: "p-1",
  tender_id: "t-1",
  status: "draft",
  format_source: "default_template",
  duration_ms: 42,
  sections: [
    {
      id: "s-1",
      section_tag: "company_profile",
      position: 0,
      content: "Annual turnover of ₹150.00 crore in FY 2024-25. [F:aaaaaaaa]",
      claims: [
        { text: "Annual turnover of ₹150.00 crore in FY 2024-25. [F:aaaaaaaa]",
          source_tag: "[F:aaaaaaaa]", status: "verified" },
      ],
      verified_pct: 100,
      dropped_untagged: 1,
      approved: false,
    },
    {
      id: "s-2",
      section_tag: "commercial_terms",
      position: 1,
      content: "All commercial terms are accepted.",
      claims: [],
      verified_pct: null,
      dropped_untagged: 0,
      approved: false,
    },
  ],
};

describe("ProposalPanel", () => {
  it("renders each section with its verified-% chip", () => {
    render(<ProposalPanel proposal={PROPOSAL} onGenerate={() => {}} busy={false} />);
    const sections = screen.getAllByTestId("proposal-section");
    expect(sections).toHaveLength(2);
    const chips = screen.getAllByTestId("verified-chip").map((c) => c.textContent);
    expect(chips).toContain("100% verified");
    expect(chips).toContain("no claims");
  });

  it("shows a per-claim verification badge and the source tag", () => {
    render(<ProposalPanel proposal={PROPOSAL} onGenerate={() => {}} busy={false} />);
    const claim = screen.getByTestId("claim");
    expect(claim).toHaveTextContent("verified");
    expect(claim).toHaveTextContent("[F:aaaaaaaa]");
  });

  it("flags how many ungrounded sentences were dropped", () => {
    render(<ProposalPanel proposal={PROPOSAL} onGenerate={() => {}} busy={false} />);
    expect(screen.getByText(/1 ungrounded dropped/)).toBeInTheDocument();
  });

  it("invites drafting when there is no proposal", () => {
    render(<ProposalPanel proposal={null} onGenerate={() => {}} busy={false} />);
    expect(screen.getByText(/once the decision is GO/)).toBeInTheDocument();
  });
});
