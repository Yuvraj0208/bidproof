"""The Conductor: the orchestrator SPEC §4 specifies, in LangGraph.

    load ─→ extract ─→ ┬─→ match       (cited judge, fans out over prose rules)
                       └─→ risk_score  (deterministic, no model)
                              ↓ join
                          decide       (deterministic EV — no model, ever)
                              ↓
                          gate_4       ██ interrupt: a human signs off

Two properties are structural here rather than enforced by convention, which
is the point of building the graph at all:

**Checkpoint 4 cannot be auto-passed.** It is not a branch the router might
take — it is an `interrupt()` with a single outgoing edge to END. There is no
path from `decide` to anything downstream that does not stop here. SPEC §7 says
checkpoints 4–6 never auto-pass; `test_gate_4_has_no_bypass` reads the compiled
graph and fails if an edge ever appears that would let one.

**Matcher and RiskScorer genuinely run together.** SPEC §4 names this pair
explicitly. It is safe because `RiskScorer` reads rules, never verdicts — see
`checking._build_risk_inputs`, which only ever touches the rule half of its
input pairs — and because the two nodes write disjoint state keys.

Worth saying plainly, because it is easy to oversell: this branch is
architecturally right but it is not where the time goes. `score_risks` is
arithmetic and returns in milliseconds. The wall-clock win in checking comes
from `checking._verdicts_for` fanning out the cited judge across prose rules
under a concurrency bound, which happens inside the `match` node.
"""

from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from app.conductor import nodes
from app.conductor.state import BidState

logger = logging.getLogger(__name__)

# Checkpoints that never auto-pass (SPEC §7). Kept as data so the test that
# guards them cannot drift from the graph that builds them.
HUMAN_ONLY_GATES = (4, 5, 6)


def build_graph(checkpointer=None):
    """Compile the check pipeline.

    A checkpointer is required for `interrupt()` to mean anything — the pause
    has to be written somewhere for the run to resume from it. When none is
    given we use the in-memory one, which is honest for this stage: the pause
    is real and the graph genuinely stops, but the resumable thread does not
    survive a restart.

    That costs nothing today because the durable record is Postgres, not the
    checkpoint: the `load` node re-derives state at the start of every run, so
    re-entering after a restart picks up exactly where the last run left off.
    A saver that outlives the process is worth building when the graph grows
    stages whose work is not already persisted (see parking-lot.md).
    """
    if checkpointer is None:
        from langgraph.checkpoint.memory import InMemorySaver

        checkpointer = InMemorySaver()

    builder = StateGraph(BidState)

    builder.add_node("load", nodes.load)
    builder.add_node("extract", nodes.extract)
    builder.add_node("match", nodes.match)
    builder.add_node("risk_score", nodes.risk_score)
    builder.add_node("decide", nodes.decide)
    builder.add_node("gate_4", nodes.gate_4)

    builder.add_edge(START, "load")
    builder.add_edge("load", "extract")

    # The fan-out: two edges out of one node puts both in the same superstep.
    builder.add_edge("extract", "match")
    builder.add_edge("extract", "risk_score")

    # The join: LangGraph waits for BOTH before `decide` starts.
    builder.add_edge("match", "decide")
    builder.add_edge("risk_score", "decide")

    builder.add_edge("decide", "gate_4")
    # The only edge out of the checkpoint. A human acting is what starts the
    # next run; nothing in the graph continues past here on its own.
    builder.add_edge("gate_4", END)

    return builder.compile(checkpointer=checkpointer)


def graph_spec() -> dict:
    """The graph as data, generated from the compiled graph itself.

    The Agent Console draws from this rather than from a hand-drawn diagram.
    A picture maintained by hand drifts from the code — the README's own
    diagram currently shows Matcher feeding RiskScorer in series, which
    contradicts SPEC §4 and is exactly the drift this avoids. A generated
    spec cannot be wrong about what runs.
    """
    compiled = build_graph().get_graph()

    edges = [
        {"from": edge.source, "to": edge.target}
        for edge in compiled.edges
    ]
    # A node reached by more than one edge in the same layer, or that shares a
    # source with a sibling, runs concurrently with that sibling.
    by_source: dict[str, list[str]] = {}
    for edge in edges:
        by_source.setdefault(edge["from"], []).append(edge["to"])
    parallel = {
        target: [t for t in targets if t != target]
        for targets in by_source.values()
        if len(targets) > 1
        for target in targets
    }

    return {
        "nodes": [
            {
                "id": name,
                "gate": int(name.split("_")[1]) if name.startswith("gate_") else None,
                "human_only": name.startswith("gate_")
                and int(name.split("_")[1]) in HUMAN_ONLY_GATES,
                "parallel_with": parallel.get(name, []),
            }
            for name in compiled.nodes
            if name not in ("__start__", "__end__")
        ],
        "edges": edges,
    }
