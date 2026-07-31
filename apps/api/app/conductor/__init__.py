"""The Conductor (SPEC §4): the orchestrator, its state, and its entrypoints.

LangGraph is imported only inside this package. Everything outside calls
`run_tender` / `graph_spec`, so the library stays swappable and the rest of the
app keeps compiling without it.
"""

from __future__ import annotations

import logging
import uuid

logger = logging.getLogger(__name__)


def conductor_available() -> bool:
    """Whether the graph can be built in this environment.

    Mirrors `adapters.browser.playwright_available()`: a heavy optional
    dependency is probed rather than assumed, so a missing install produces a
    clear 503 instead of an import error at request time.
    """
    try:
        import langgraph  # noqa: F401

        return True
    except ImportError:
        return False


def graph_spec() -> dict:
    """The graph as data, for the Agent Console. Generated, never hand-drawn."""
    from app.conductor.graph import graph_spec as _spec

    return _spec()


async def run_tender(org_id: uuid.UUID, tender_id: uuid.UUID,
                     gateway=None) -> dict:
    """Run the check pipeline through the graph, stopping at checkpoint 4.

    Returns what the run did and where it stopped. It always stops: SPEC §7
    gives the bid decision to a human, so reaching the end of this function
    without a pause would be a bug, not a success.

    `gateway` is the caller's — normally the request's FastAPI dependency, so
    a test's stub reaches the graph the same way it reaches the sequential
    path. Nodes never build their own.
    """
    from app.conductor.graph import build_graph
    from app.conductor.state import BidState

    graph = build_graph()
    final = await graph.ainvoke(
        BidState(org_id=org_id, tender_id=tender_id),
        # One thread per tender, so a resumed run continues the same run
        # rather than starting a parallel one.
        config={
            "configurable": {"thread_id": str(tender_id), "gateway": gateway},
            "recursion_limit": 40,
        },
    )

    if isinstance(final, dict):
        # An interrupted run reports the pause alongside the state, and the
        # graph may carry its own bookkeeping channels. The state schema
        # forbids unknown fields on purpose — that strictness is what rejects a
        # malformed node return — so read the fields we declared and let the
        # library keep its own.
        interrupted = bool(final.get("__interrupt__"))
        state = BidState.model_validate(
            {k: v for k, v in final.items() if k in BidState.model_fields}
        )
        if interrupted:
            state.paused_at = 4
    else:
        state = final

    counts: dict[str, int] = {}
    for verdict in state.verdicts:
        counts[verdict.verdict] = counts.get(verdict.verdict, 0) + 1

    # The Conductor's own row in the ledger. Without it the Agent Console shows
    # the agents but not the orchestration, and `paused_at` — which lives only
    # in graph state — would never survive the request.
    from app.observability import record_agent_run

    steps = {step.node: step for step in state.trace}
    await record_agent_run(
        org_id,
        tender_id,
        "conductor",
        duration_ms=sum(step.duration_ms for step in state.trace),
        meta={
            "nodes": [step.node for step in state.trace],
            "paused_at": state.paused_at,
            "parallel": sorted(
                {
                    node
                    for node, step in steps.items()
                    if step.parallel_with
                }
            ),
            # Wall-clock against the sum of the branch durations: the honest
            # way to report the parallel branch, including when it saves
            # nothing because both sides are fast.
            "concurrent_ms_saved": max(
                0,
                sum(
                    step.duration_ms
                    for step in state.trace
                    if step.parallel_with
                )
                - max(
                    (
                        step.duration_ms
                        for step in state.trace
                        if step.parallel_with
                    ),
                    default=0,
                ),
            ),
        },
    )

    return {
        "tender_id": str(tender_id),
        "rules": len(state.rules),
        "verdict_counts": counts,
        "risks": len(state.risks),
        "model_calls": sum(step.model_calls for step in state.trace),
        # The graph stops at checkpoint 4 rather than running to completion,
        # so `paused_at` is the expected outcome of a healthy run.
        "paused_at": state.paused_at,
        "trace": [step.model_dump() for step in state.trace],
    }
