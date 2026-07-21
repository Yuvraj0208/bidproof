// US-10: export is refused while blockers exist; the override needs a name
// and a written reason.
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ExportBar } from "./ExportBar";
import type { ExportBlocker } from "../api";

const BLOCKERS: ExportBlocker[] = [
  { type: "unaddressed_mandatory_clause", rule_key: "min_turnover",
    message: "mandatory clause 'min_turnover' is needs_human" },
  { type: "contradicted_claim", section: "company_profile",
    message: "section 'company_profile' contains a contradicted claim" },
];

describe("ExportBar", () => {
  it("refuses export and lists the blockers", () => {
    render(<ExportBar blockers={BLOCKERS} onExport={() => {}}
                      onOverride={() => {}} busy={false} />);
    expect(screen.getByTestId("export-status")).toHaveTextContent(
      "refused — 2 blocker(s)",
    );
    expect(screen.getByTestId("export-button")).toBeDisabled();
    const list = screen.getByTestId("blocker-list");
    expect(list).toHaveTextContent("unaddressed mandatory clause");
    expect(list).toHaveTextContent("contradicted claim");
  });

  it("gates the override on a name and a written reason", () => {
    const onOverride = vi.fn();
    render(<ExportBar blockers={BLOCKERS} onExport={() => {}}
                      onOverride={onOverride} busy={false} />);
    const button = screen.getByTestId("override-button");
    expect(button).toBeDisabled();

    fireEvent.change(screen.getByPlaceholderText("Your name"),
                     { target: { value: "Bid Head" } });
    expect(button).toBeDisabled();            // still needs a reason
    fireEvent.change(screen.getByPlaceholderText("Written reason (required)"),
                     { target: { value: "client confirmed by email" } });
    expect(button).toBeEnabled();
    fireEvent.click(button);
    expect(onOverride).toHaveBeenCalledWith("Bid Head", "client confirmed by email");
  });

  it("allows a clean export when there are no blockers", () => {
    const onExport = vi.fn();
    render(<ExportBar blockers={[]} onExport={onExport}
                      onOverride={() => {}} busy={false} />);
    expect(screen.getByTestId("export-status")).toHaveTextContent("ready to export");
    const button = screen.getByTestId("export-button");
    expect(button).toBeEnabled();
    fireEvent.click(button);
    expect(onExport).toHaveBeenCalled();
    // no override form when nothing is blocked
    expect(screen.queryByTestId("override-button")).toBeNull();
  });
});
