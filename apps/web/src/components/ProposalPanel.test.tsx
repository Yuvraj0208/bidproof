// US-09 + US-11: sections render with claim badges, three scores, and
// individual approval that is blocked while a flag is open.
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProposalPanel } from "./ProposalPanel";
import type { Proposal, ProposalSection } from "../api";

const clean: ProposalSection = {
  id: "s-1",
  section_tag: "company_profile",
  position: 0,
  content: "Annual turnover of ₹150.00 crore in FY 2024-25. [F:aaaaaaaa]",
  content_display: "Annual turnover of ₹150.00 crore in FY 2024-25.",
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
  // The approver's name is remembered across reloads, so it must not leak
  // between tests — one test's name would silently enable another's button.
  beforeEach(() => localStorage.clear());

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

    // Per-section approval still works on its own; the selection bar only
    // appears when the panel is given a bulk handler.
    expect(screen.queryByTestId("approve-selected")).toBeNull();
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

  it("selects sections and approves them with one button and one name", () => {
    const onApproveMany = vi.fn();
    render(<ProposalPanel proposal={PROPOSAL} onGenerate={() => {}}
                          onApprove={() => {}} onApproveMany={onApproveMany}
                          busy={false} />);
    fireEvent.change(screen.getByPlaceholderText(/Your name/),
                     { target: { value: "Priya N" } });

    // Only the clean section is selectable; the flagged one is not.
    fireEvent.click(screen.getByTestId("select-all-sections"));
    fireEvent.click(screen.getByTestId("approve-selected"));

    expect(onApproveMany).toHaveBeenCalledWith(["s-1"], "Priya N");
  });

  it("will not let a flagged section be selected for bulk approval", () => {
    // The bulk path must not become a way to sign off a contradicted claim.
    render(<ProposalPanel proposal={PROPOSAL} onGenerate={() => {}}
                          onApprove={() => {}} onApproveMany={() => {}}
                          busy={false} />);
    expect(screen.getByTestId("select-technical_approach")).toBeDisabled();
    expect(screen.getByTestId("select-company_profile")).toBeEnabled();
    expect(screen.getByTestId("blocked-note")).toHaveTextContent(
      "1 section(s) not selectable",
    );
  });

  it("needs a name before the bulk button works", () => {
    render(<ProposalPanel proposal={PROPOSAL} onGenerate={() => {}}
                          onApprove={() => {}} onApproveMany={() => {}}
                          busy={false} />);
    fireEvent.click(screen.getByTestId("select-all-sections"));
    expect(screen.getByTestId("approve-selected")).toBeDisabled();
  });

  it("offers a way to resolve a flagged claim", () => {
    // The bug this covers: the approve button said "resolve open flags first"
    // and nothing in the product could resolve one. The section could not be
    // approved and could not be exported — a dead end.
    const onResolveClaim = vi.fn();
    render(<ProposalPanel proposal={PROPOSAL} onGenerate={() => {}}
                          onApprove={() => {}} onResolveClaim={onResolveClaim}
                          busy={false} />);
    fireEvent.change(screen.getByPlaceholderText(/Your name/),
                     { target: { value: "Priya N" } });

    fireEvent.click(screen.getByTestId("claim-drop"));
    expect(onResolveClaim).toHaveBeenCalledWith("s-2", 0, "drop", "Priya N", "");
  });

  it("asks for a written reason before keeping a contradicted claim", () => {
    // Removing an unproven sentence is the safe direction and needs no
    // justification. Keeping one in a bid document is the decision that does.
    const onResolveClaim = vi.fn();
    render(<ProposalPanel proposal={PROPOSAL} onGenerate={() => {}}
                          onApprove={() => {}} onResolveClaim={onResolveClaim}
                          busy={false} />);
    fireEvent.change(screen.getByPlaceholderText(/Your name/),
                     { target: { value: "Priya N" } });

    fireEvent.click(screen.getByTestId("claim-accept"));
    const confirm = screen.getByTestId("claim-accept-confirm");
    expect(confirm).toBeDisabled();

    fireEvent.change(screen.getByPlaceholderText(/Why is this claim right/),
                     { target: { value: "Certificate renewed, not yet loaded" } });
    expect(confirm).toBeEnabled();
    fireEvent.click(confirm);
    expect(onResolveClaim).toHaveBeenCalledWith(
      "s-2", 0, "accept", "Priya N",
      "Certificate renewed, not yet loaded",
    );
  });

  it("cannot resolve a claim without a name", () => {
    render(<ProposalPanel proposal={PROPOSAL} onGenerate={() => {}}
                          onApprove={() => {}} onResolveClaim={() => {}}
                          busy={false} />);
    expect(screen.getByTestId("claim-drop")).toBeDisabled();
  });

  it("shows who resolved a claim, and stops offering to resolve it again", () => {
    const resolved: Proposal = {
      ...PROPOSAL,
      sections: [{
        ...flagged,
        claims: [{ ...flagged.claims[0], resolution: "accept",
                   resolved_by: "Priya N" }],
        open_flags: [],
      }],
    };
    render(<ProposalPanel proposal={resolved} onGenerate={() => {}}
                          onApprove={() => {}} onResolveClaim={() => {}}
                          busy={false} />);
    expect(screen.getByTestId("claim-resolved")).toHaveTextContent(
      "accepted by Priya N",
    );
    expect(screen.queryByTestId("claim-drop")).toBeNull();
  });

  it("remembers the approver's name across reloads", () => {
    const { unmount } = render(
      <ProposalPanel proposal={PROPOSAL} onGenerate={() => {}}
                     onApprove={() => {}} busy={false} />,
    );
    fireEvent.change(screen.getByPlaceholderText(/Your name/),
                     { target: { value: "Priya N" } });
    unmount();

    render(<ProposalPanel proposal={PROPOSAL} onGenerate={() => {}}
                          onApprove={() => {}} busy={false} />);
    expect(screen.getByPlaceholderText(/Your name/)).toHaveValue("Priya N");
    expect(screen.getAllByTestId("approve-button")).toHaveLength(2);
  });

  it("never shows the internal source tags in the prose", () => {
    // The tag is the proof chain and stays in `content`; a buyer reading
    // "[F:aaaaaaaa]" mid-sentence sees a broken document.
    render(<ProposalPanel proposal={PROPOSAL} onGenerate={() => {}}
                          onApprove={() => {}} busy={false} />);
    const prose = screen.getAllByTestId("section-prose")[0];
    expect(prose.textContent).not.toContain("[F:");
    expect(prose.textContent).toContain("FY 2024-25.");
    // The provenance is still shown, as structured data beside the prose.
    expect(screen.getAllByTestId("claim")[0].textContent).toContain("[F:aaaaaaaa]");
  });
});
