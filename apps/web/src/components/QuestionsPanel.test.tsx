// US-08: the pack shows a cited letter per failed rule, with no send action.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { QuestionsPanel } from "./QuestionsPanel";
import type { QueryLetter } from "../api";

const LETTER: QueryLetter = {
  id: "q-1",
  rule_id: "r-1",
  rule_key: "required_standard",
  el_id: "el-9",
  page_no: 1,
  subject: "Pre-bid query — clause 'required_standard' (page 1)",
  body:
    "To,\nThe Tender Inviting Authority\n\n... requirement stated on page 1 ...\n" +
    "We respectfully request the Authority to consider relaxing ...",
  query_deadline: "2026-08-18",
  status: "draft",
};

describe("QuestionsPanel", () => {
  it("shows a cited letter per failed rule", () => {
    render(<QuestionsPanel letters={[LETTER]} onGenerate={() => {}} busy={false} />);
    const letter = screen.getByTestId("query-letter");
    expect(letter).toHaveTextContent("required_standard");
    expect(letter).toHaveTextContent("cites p.1");
    expect(letter).toHaveTextContent("before 2026-08-18");
    expect(letter).toHaveTextContent("draft");
    expect(letter).toHaveTextContent("page 1");
  });

  it("offers no send action — drafts only", () => {
    render(<QuestionsPanel letters={[LETTER]} onGenerate={() => {}} busy={false} />);
    const buttons = screen.getAllByRole("button").map((b) => b.textContent?.toLowerCase());
    expect(buttons.some((t) => t?.includes("send") || t?.includes("submit"))).toBe(
      false,
    );
  });

  it("shows the empty state with no letters", () => {
    render(<QuestionsPanel letters={[]} onGenerate={() => {}} busy={false} />);
    expect(screen.getByText(/No queries drafted/)).toBeInTheDocument();
  });
});
