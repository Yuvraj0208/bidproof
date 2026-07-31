// The Conductor's graph, drawn from the shape the API generates out of the
// compiled graph itself.
//
// The layout is computed from the edges rather than hard-coded, for the same
// reason the API generates the spec: a picture maintained by hand drifts from
// the code it claims to describe. If someone reorders the pipeline, this
// redraws. If someone removes the human checkpoint, the gate disappears from
// the screen — which is exactly the signal you would want.

export interface GraphNode {
  id: string;
  gate: number | null;
  human_only: boolean;
  parallel_with: string[];
}

export interface GraphEdge {
  from: string;
  to: string;
}

export interface PipelineGraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

// Node ids are pipeline stages; agent_runs rows are named after the agents
// that run in them. One map, so the console can colour a node by what actually
// happened rather than guessing from the name.
const NODE_AGENT: Record<string, string> = {
  extract: "extractor",
  match: "matcher",
  risk_score: "riskscorer",
  decide: "decider",
};

const LABEL: Record<string, string> = {
  load: "Load rules",
  extract: "Extractor",
  match: "Matcher",
  risk_score: "RiskScorer",
  decide: "Decider",
};

function gateLabel(gate: number): string {
  return `Checkpoint ${gate}`;
}

/** Longest-path layering: a node sits one column right of its latest input. */
export function layerNodes(data: PipelineGraphData): string[][] {
  const incoming = new Map<string, string[]>();
  data.nodes.forEach((n) => incoming.set(n.id, []));
  data.edges.forEach((e) => {
    if (incoming.has(e.to) && incoming.has(e.from)) {
      incoming.get(e.to)!.push(e.from);
    }
  });

  const depth = new Map<string, number>();
  const resolve = (id: string, seen: Set<string>): number => {
    if (depth.has(id)) return depth.get(id)!;
    if (seen.has(id)) return 0; // a cycle would be a bug, but never hang on it
    seen.add(id);
    const parents = incoming.get(id) ?? [];
    const value = parents.length
      ? Math.max(...parents.map((p) => resolve(p, seen))) + 1
      : 0;
    depth.set(id, value);
    return value;
  };
  data.nodes.forEach((n) => resolve(n.id, new Set()));

  const columns: string[][] = [];
  data.nodes.forEach((n) => {
    const d = depth.get(n.id) ?? 0;
    (columns[d] ??= []).push(n.id);
  });
  return columns.filter(Boolean);
}

export function PipelineGraph({
  data,
  ranAgents,
  pausedAt,
}: {
  data: PipelineGraphData;
  // Agents with a recorded run for this tender, so a node can show it ran.
  ranAgents: Set<string>;
  pausedAt: number | null;
}) {
  const columns = layerNodes(data);
  const byId = new Map(data.nodes.map((n) => [n.id, n]));

  return (
    <div
      data-testid="pipeline-graph"
      className="mb-5 overflow-x-auto rounded-[12px] border border-hairline bg-white p-4"
    >
      <div className="mb-3 flex items-baseline gap-2">
        <h3 className="text-sm font-semibold text-ink">Pipeline</h3>
        <span className="text-[11px] text-ink-subtle">
          drawn from the running graph, not a diagram
        </span>
      </div>

      <div className="flex min-w-max items-stretch gap-1">
        {columns.map((column, index) => (
          <div key={index} className="flex items-center gap-1">
            <div className="flex flex-col justify-center gap-1.5">
              {column.map((id) => {
                const node = byId.get(id)!;
                const agent = NODE_AGENT[id];
                const ran = agent ? ranAgents.has(agent) : false;
                const waiting = node.gate !== null && pausedAt === node.gate;

                return (
                  <div
                    key={id}
                    data-testid={`graph-node-${id}`}
                    data-ran={ran || undefined}
                    title={
                      node.human_only
                        ? "A human decides here. The graph has no path around it."
                        : node.parallel_with.length
                          ? `Runs at the same time as ${node.parallel_with.join(", ")}`
                          : undefined
                    }
                    className={[
                      "rounded-[8px] border px-3 py-2 text-xs whitespace-nowrap",
                      node.human_only
                        ? "border-warning bg-warning-tint font-medium text-ink"
                        : ran
                          ? "border-indigo bg-indigo-tint text-indigo"
                          : "border-hairline bg-surface text-ink-muted",
                    ].join(" ")}
                  >
                    {node.gate !== null ? (
                      <span className="flex items-center gap-1.5">
                        <span aria-hidden>■</span>
                        {gateLabel(node.gate)}
                        {waiting && (
                          <span className="text-[10px] font-normal">
                            · waiting for you
                          </span>
                        )}
                      </span>
                    ) : (
                      LABEL[id] ?? id
                    )}
                    {node.parallel_with.length > 0 && (
                      <span className="ml-1.5 text-[10px] text-ink-subtle">
                        ∥
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
            {index < columns.length - 1 && (
              <span aria-hidden className="px-0.5 text-ink-subtle">
                →
              </span>
            )}
          </div>
        ))}
      </div>

      <p className="mt-3 text-[11px] text-ink-subtle">
        <span className="text-ink-muted">∥</span> runs at the same time ·{" "}
        <span className="text-ink-muted">■</span> a human decides, and the graph
        has no path around it
      </p>
    </div>
  );
}
