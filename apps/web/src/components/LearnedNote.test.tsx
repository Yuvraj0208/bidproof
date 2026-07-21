// US-20: the learned pre-fill is shown with its value and a visible provenance
// note citing the source tender — never silent.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LearnedNote } from "./LearnedNote";

describe("LearnedNote", () => {
  it("shows the suggested value and the provenance note", () => {
    render(
      <LearnedNote
        learned={{
          suggested_value: "consortium allowed with lead partner 51%",
          note: "Based on your correction on Tender #GEM-1099",
          based_on_count: 2,
          source_tender_id: "t-1099",
        }}
      />,
    );
    const note = screen.getByTestId("learned-note");
    expect(note).toHaveTextContent("consortium allowed with lead partner 51%");
    expect(note).toHaveTextContent("Based on your correction on Tender #GEM-1099");
    expect(note).toHaveTextContent("2 past corrections");
  });
});
