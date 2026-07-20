// US-12: the console renders every run and the totals line.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  AgentConsole,
  totalsLine,
  type AgentRunData,
} from "./AgentConsole";

const RUN = (agent: string, ms: number): AgentRunData => ({
  id: agent,
  agent,
  status: "ok",
  model_role: agent === "extractor" ? "mid" : null,
  prompt_version: agent === "extractor" ? "extractor_v1" : null,
  tokens_in: 0,
  tokens_out: 0,
  cost_inr: 0,
  duration_ms: ms,
  meta: {},
  created_at: "2026-07-20T10:00:00Z",
});

describe("AgentConsole", () => {
  it("formats the totals line — the business-case line", () => {
    expect(
      totalsLine({ calls: 14, tokens: 213000, cost_inr: 38.4, duration_ms: 372000 }),
    ).toBe("14 agent calls · 2,13,000 tokens · ₹38.40 · 372.0 s");
  });

  it("renders one row per agent run with role and prompt version", () => {
    render(
      <AgentConsole
        runs={[RUN("parser", 900), RUN("triage", 40), RUN("extractor", 120)]}
        totals={{ calls: 3, tokens: 0, cost_inr: 0, duration_ms: 1060 }}
        onReplay={() => {}}
        replaying={false}
      />,
    );
    expect(screen.getAllByTestId("agent-run")).toHaveLength(3);
    expect(screen.getByTestId("totals-line")).toHaveTextContent(
      "3 agent calls",
    );
    expect(screen.getByText("role: mid")).toBeInTheDocument();
    expect(screen.getByText("extractor_v1")).toBeInTheDocument();
  });
});
