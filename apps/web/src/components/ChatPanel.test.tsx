// US-15: answers show page citations; refusals are styled distinctly;
// sending a question invokes the handler.
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ChatPanel } from "./ChatPanel";
import type { ChatTurn } from "../api";

const TURNS: ChatTurn[] = [
  { role: "user", content: "What is the EMD?", citations: [], refused: false,
    reason: null },
  { role: "assistant", content: 'On page 1: "Earnest Money Deposit: Rs 2,50,000"',
    citations: [{ el_id: "el-1", page_no: 1 }], refused: false, reason: null },
  { role: "user", content: "What is the weather?", citations: [], refused: false,
    reason: null },
  { role: "assistant", content: "I can only discuss the tenders in this workspace.",
    citations: [], refused: true, reason: "out_of_scope" },
];

describe("ChatPanel", () => {
  it("shows an answer with its page citations", () => {
    render(<ChatPanel turns={TURNS} onAsk={() => {}} busy={false} />);
    expect(screen.getByTestId("citations")).toHaveTextContent("page 1");
    expect(screen.getByText(/Earnest Money Deposit/)).toBeInTheDocument();
  });

  it("marks a refusal distinctly", () => {
    render(<ChatPanel turns={TURNS} onAsk={() => {}} busy={false} />);
    expect(
      screen.getByText(/only discuss the tenders in this workspace/),
    ).toBeInTheDocument();
  });

  it("sends a question", () => {
    const onAsk = vi.fn();
    render(<ChatPanel turns={[]} onAsk={onAsk} busy={false} />);
    fireEvent.change(screen.getByPlaceholderText(/Ask about this tender/),
                     { target: { value: "Which rules do we fail?" } });
    fireEvent.click(screen.getByTestId("chat-send"));
    expect(onAsk).toHaveBeenCalledWith("Which rules do we fail?");
  });
});
