// The pipeline diagram is generated from the running graph, so these tests
// are about the two things a picture can get wrong: putting concurrent work in
// series, and letting the human checkpoint look optional.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PipelineGraph, layerNodes, type PipelineGraphData } from "./PipelineGraph";

// The shape the API returns for the check pipeline.
const GRAPH: PipelineGraphData = {
  nodes: [
    { id: "load", gate: null, human_only: false, parallel_with: [] },
    { id: "extract", gate: null, human_only: false, parallel_with: [] },
    { id: "match", gate: null, human_only: false, parallel_with: ["risk_score"] },
    { id: "risk_score", gate: null, human_only: false, parallel_with: ["match"] },
    { id: "decide", gate: null, human_only: false, parallel_with: [] },
    { id: "gate_4", gate: 4, human_only: true, parallel_with: [] },
  ],
  edges: [
    { from: "load", to: "extract" },
    { from: "extract", to: "match" },
    { from: "extract", to: "risk_score" },
    { from: "match", to: "decide" },
    { from: "risk_score", to: "decide" },
    { from: "decide", to: "gate_4" },
  ],
};

describe("layerNodes", () => {
  it("puts concurrent agents in the same column", () => {
    const columns = layerNodes(GRAPH);
    const column = columns.find((c) => c.includes("match"));
    expect(column).toContain("risk_score");
  });

  it("places a node after its slowest input, not its first", () => {
    // decide has two parents; it must sit to the right of BOTH, or the picture
    // would imply it can start before the risk scorer finishes.
    const columns = layerNodes(GRAPH);
    const depth = (id: string) => columns.findIndex((c) => c.includes(id));
    expect(depth("decide")).toBeGreaterThan(depth("match"));
    expect(depth("decide")).toBeGreaterThan(depth("risk_score"));
    expect(depth("gate_4")).toBeGreaterThan(depth("decide"));
  });

  it("survives a graph with no edges rather than hanging", () => {
    const columns = layerNodes({ nodes: GRAPH.nodes, edges: [] });
    expect(columns).toHaveLength(1);
    expect(columns[0]).toHaveLength(6);
  });
});

describe("PipelineGraph", () => {
  it("shows the human checkpoint as a gate", () => {
    render(<PipelineGraph data={GRAPH} ranAgents={new Set()} pausedAt={null} />);
    expect(screen.getByTestId("graph-node-gate_4")).toHaveTextContent(
      "Checkpoint 4",
    );
  });

  it("says the checkpoint is waiting when the run stopped there", () => {
    render(<PipelineGraph data={GRAPH} ranAgents={new Set()} pausedAt={4} />);
    expect(screen.getByTestId("graph-node-gate_4")).toHaveTextContent(
      "waiting for you",
    );
  });

  it("marks the agents that actually ran", () => {
    render(
      <PipelineGraph
        data={GRAPH}
        ranAgents={new Set(["matcher", "riskscorer"])}
        pausedAt={4}
      />,
    );
    // Node ids are stages; agent_runs rows are named after agents. A node
    // showing as "ran" when nothing ran would be the console lying.
    expect(screen.getByTestId("graph-node-match")).toHaveAttribute("data-ran");
    expect(screen.getByTestId("graph-node-risk_score")).toHaveAttribute(
      "data-ran",
    );
    expect(screen.getByTestId("graph-node-decide")).not.toHaveAttribute(
      "data-ran",
    );
  });

  it("renders every node the graph reports, so a new stage cannot hide", () => {
    render(<PipelineGraph data={GRAPH} ranAgents={new Set()} pausedAt={null} />);
    for (const node of GRAPH.nodes) {
      expect(screen.getByTestId(`graph-node-${node.id}`)).toBeInTheDocument();
    }
  });
});
