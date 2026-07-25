// Ask BidProof (US-15): a scoped chat inside the tender workspace. It answers
// only from this tender's elements and cites the page; out-of-scope and
// jailbreak questions are refused.
import { useState } from "react";
import type { ChatTurn } from "../api";

export function ChatPanel({
  turns,
  onAsk,
  busy,
}: {
  turns: ChatTurn[];
  onAsk: (question: string) => void;
  busy: boolean;
}) {
  const [question, setQuestion] = useState("");

  const send = () => {
    if (question.trim()) {
      onAsk(question.trim());
      setQuestion("");
    }
  };

  return (
    <div className="mx-auto flex h-full max-w-2xl flex-col p-6">
      <h2 className="mb-1 text-sm font-semibold text-ink">Ask BidProof</h2>
      <p className="mb-3 text-xs text-ink-subtle">
        Answers come only from this tender, with page citations. Questions
        outside it are refused.
      </p>

      <div className="min-h-0 flex-1 space-y-3 overflow-auto" data-testid="chat-log">
        {turns.length === 0 && (
          <p className="text-sm text-ink-muted">
            Ask about this tender — for example, “What is the EMD?”
          </p>
        )}
        {turns.map((turn, i) => (
          <div
            key={i}
            data-testid={`turn-${turn.role}`}
            className={turn.role === "user" ? "text-right" : ""}
          >
            <div
              className={`inline-block max-w-[85%] rounded-[12px] px-3 py-2 text-sm ${
                turn.role === "user"
                  ? "bg-indigo text-white"
                  : turn.refused
                    ? "bg-danger-tint text-danger"
                    : "bg-white text-ink"
              }`}
            >
              <div className="whitespace-pre-wrap">{turn.content}</div>
              {turn.citations.length > 0 && (
                <div
                  data-testid="citations"
                  className="mt-1 flex flex-wrap gap-1 text-[11px] text-ink-subtle"
                >
                  {turn.citations.map((c, j) => (
                    <span key={j} className="rounded-[8px] bg-surface px-1.5">
                      page {c.page_no}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-3 flex gap-2">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Ask about this tender…"
          className="flex-1 rounded-[8px] border border-hairline px-2 py-1 text-sm"
        />
        <button
          data-testid="chat-send"
          onClick={send}
          disabled={busy || !question.trim()}
          className="rounded-[8px] bg-indigo px-3 py-1 text-sm font-medium text-white disabled:opacity-40"
        >
          {busy ? "…" : "Ask"}
        </button>
      </div>
    </div>
  );
}
