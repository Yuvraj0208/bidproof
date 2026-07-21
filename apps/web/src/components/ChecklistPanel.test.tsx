// US-18: items show the system's checks; tick is blocked until checks pass
// and a name is given; submit-ready reflects the ticks.
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ChecklistPanel } from "./ChecklistPanel";
import type { Checklist, ChecklistItem } from "../api";

function item(over: Partial<ChecklistItem> = {}): ChecklistItem {
  return {
    id: "i-1", name: "Technical Bid", required: true, required_format: "pdf",
    signature_required: true, uploaded_format: null, signature_present: null,
    checks_pass: false, checks_reason: "no file attached yet",
    ticked: false, ticked_by: null, ...over,
  };
}

function checklist(items: ChecklistItem[]): Checklist {
  const ticked = items.filter((i) => i.ticked).length;
  return {
    items,
    required_count: items.length,
    ticked_count: ticked,
    submit_ready: items.length > 0 && ticked === items.length,
  };
}

describe("ChecklistPanel", () => {
  it("blocks ticking until the checks pass", () => {
    render(<ChecklistPanel checklist={checklist([item()])} name="Priya N"
             onName={() => {}} onAttach={() => {}} onTick={() => {}}
             onGenerate={() => {}} />);
    expect(screen.getByTestId("checks-status")).toHaveTextContent("no file");
    expect(screen.getByTestId("tick-button")).toBeDisabled();
  });

  it("allows ticking once checks pass and a name is present", () => {
    const onTick = vi.fn();
    render(<ChecklistPanel
             checklist={checklist([item({ checks_pass: true,
                                          uploaded_format: "pdf",
                                          signature_present: true })])}
             name="Priya N" onName={() => {}} onAttach={() => {}}
             onTick={onTick} onGenerate={() => {}} />);
    const tick = screen.getByTestId("tick-button");
    expect(tick).toBeEnabled();
    fireEvent.click(tick);
    expect(onTick).toHaveBeenCalledWith("i-1");
  });

  it("disables ticking when no name is given", () => {
    render(<ChecklistPanel
             checklist={checklist([item({ checks_pass: true })])}
             name="" onName={() => {}} onAttach={() => {}} onTick={() => {}}
             onGenerate={() => {}} />);
    expect(screen.getByTestId("tick-button")).toBeDisabled();
  });

  it("shows submit-ready only when everything is ticked", () => {
    const done = checklist([item({ ticked: true, ticked_by: "Priya N",
                                   checks_pass: true })]);
    render(<ChecklistPanel checklist={done} name="Priya N" onName={() => {}}
             onAttach={() => {}} onTick={() => {}} onGenerate={() => {}} />);
    expect(screen.getByTestId("submit-status")).toHaveTextContent("submit-ready");
    expect(screen.getByTestId("ticked-badge")).toHaveTextContent("Priya N");
  });
});
