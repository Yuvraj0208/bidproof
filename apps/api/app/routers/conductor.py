"""The Conductor's read surface: the graph, and what the last run did.

Two endpoints, and the split between them is deliberate.

`/conductor/graph` is the pipeline's *shape* — generated from the compiled
graph, never hand-written. A diagram maintained by hand drifts from the code it
claims to describe; this one cannot, because it is read out of the thing that
actually runs.

`/tenders/{id}/conductor/run` is what *happened* — the per-node trace of the
most recent run, read from `agent_runs`, which already records model role,
tokens, rupees and latency per agent (SPEC §13).

Starting a run stays on `POST /tenders/{id}/process`, which is the one route
that may spend money (FINISH_STATUS R2). Adding a second way to trigger spend
would defeat the point of having one.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select

from app.conductor import conductor_available, graph_spec
from app.core.db import org_scoped_session
from app.core.tenancy import require_org_id
from app.models import AgentRun

router = APIRouter()

# The order nodes appear in the pipeline, for a UI that wants to lay them out
# left to right. Derived from the graph, not hard-coded, in `graph_spec()`.
UNAVAILABLE = (
    "the Conductor needs the langgraph package; install the API dependencies "
    "and restart"
)


class GraphNode(BaseModel):
    id: str
    gate: int | None
    human_only: bool
    parallel_with: list[str]


class GraphOut(BaseModel):
    nodes: list[GraphNode]
    # `from` is a Python keyword, so the edges stay plain dicts rather than
    # forcing an alias the frontend would have to know about.
    edges: list[dict]


@router.get("/conductor/graph", response_model=GraphOut)
async def get_graph() -> GraphOut:
    """The pipeline's shape, generated from the compiled graph."""
    if not conductor_available():
        raise HTTPException(503, UNAVAILABLE)
    spec = graph_spec()
    return GraphOut(
        nodes=[GraphNode(**node) for node in spec["nodes"]],
        edges=spec["edges"],
    )


class NodeRun(BaseModel):
    agent: str
    duration_ms: int | None
    model_role: str | None
    cost_inr: float | None
    meta: dict


class RunOut(BaseModel):
    tender_id: uuid.UUID
    nodes: list[NodeRun]
    total_cost_inr: float
    # Which checkpoint the run is waiting at, if any. None means it has not
    # reached one — never "it finished", because reaching the end without a
    # human would itself be the bug.
    paused_at: int | None


@router.get("/tenders/{tender_id}/conductor/run", response_model=RunOut)
async def get_run(
    tender_id: uuid.UUID,
    org_id: uuid.UUID = Depends(require_org_id),
) -> RunOut:
    """What the most recent run did, per node."""
    async with org_scoped_session(org_id) as session:
        rows = (
            await session.execute(
                select(AgentRun)
                .where(AgentRun.tender_id == tender_id)
                .order_by(desc(AgentRun.created_at))
                .limit(40)
            )
        ).scalars().all()

    nodes = [
        NodeRun(
            agent=row.agent,
            duration_ms=row.duration_ms,
            model_role=row.model_role,
            cost_inr=float(row.cost_inr) if row.cost_inr is not None else None,
            meta=row.meta or {},
        )
        for row in rows
    ]
    paused = next(
        (n.meta.get("paused_at") for n in nodes if n.meta.get("paused_at")), None
    )
    return RunOut(
        tender_id=tender_id,
        nodes=nodes,
        total_cost_inr=round(sum(n.cost_inr or 0.0 for n in nodes), 4),
        paused_at=paused,
    )
