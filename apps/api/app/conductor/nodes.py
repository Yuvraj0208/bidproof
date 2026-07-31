"""Graph nodes: thin adapters over the services that already do the work.

The rule this module exists to obey: **a node contains no logic.** It calls one
existing service function and maps the result into typed state. The moment a
node starts deciding something, the Conductor has become a second
implementation of the pipeline and the two will drift — which is the failure
this whole design is meant to avoid, one layer up.

So arithmetic still lives in `bidproof_decider` and `bidproof_matcher`,
persistence still lives in the services, and this file stays boring.
"""

from __future__ import annotations

import logging
import time
import uuid

from langgraph.types import interrupt
from sqlalchemy import select

from app.conductor.state import BidState, Gate, NodeTrace, RiskRef, RuleRef, VerdictRef
from app.core.db import org_scoped_session
from app.models import RiskRow, Rule, VerdictRow

logger = logging.getLogger(__name__)


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


async def load(state: BidState) -> dict:
    """Re-derive rules from Postgres.

    This is what makes a run resumable without holding anything open: the
    database is the truth, so re-entering the graph after a human acts picks up
    the same state the previous run left behind.
    """
    started = time.monotonic()
    async with org_scoped_session(state.org_id) as session:
        rows = (
            await session.execute(
                select(Rule).where(Rule.tender_id == state.tender_id)
            )
        ).scalars().all()

    rules = [
        RuleRef(
            rule_id=row.rule_id,
            family=row.family,
            key=row.key,
            el_id=row.el_id,
            band=row.band or "green",
        )
        for row in rows
        # Golden rule 4: a rule with no element cannot be shown or proved, so
        # it does not enter the graph at all.
        if row.el_id is not None
    ]
    return {
        "rules": rules,
        "trace": [NodeTrace(node="load", duration_ms=_elapsed_ms(started))],
    }


async def extract(state: BidState) -> dict:
    """Rules are extracted by the existing service before the graph runs.

    Kept as a node so the Console shows extraction in the same picture as the
    rest, and so the graph has a single place to grow into when extraction
    moves inside it.
    """
    started = time.monotonic()
    return {
        "trace": [
            NodeTrace(
                node="extract",
                duration_ms=_elapsed_ms(started),
                model_role="mid" if state.rules else None,
            )
        ]
    }


async def match(state: BidState, config=None) -> dict:
    """The Matcher: arithmetic first, then the cited judge over prose rules.

    Runs concurrently with `risk_score`. The fan-out across individual prose
    rules — the part that actually saves time — happens inside
    `checking._verdicts_for`, under `LLM_MAX_CONCURRENCY`.

    The gateway arrives through the run config rather than being constructed
    here. That matters for more than tidiness: the request's gateway is a
    FastAPI dependency, and `dependency_overrides` only reach `Depends(...)`.
    A node that built its own would quietly ignore the tests' stub and put real
    calls on the wire during the test suite.
    """
    from app.services import checking

    started = time.monotonic()
    gateway = (config or {}).get("configurable", {}).get("gateway")
    summary = await checking.run_matcher(
        state.org_id, state.tender_id, gateway=gateway
    )

    async with org_scoped_session(state.org_id) as session:
        rows = (
            await session.execute(
                select(VerdictRow).where(VerdictRow.tender_id == state.tender_id)
            )
        ).scalars().all()

    return {
        "verdicts": [
            VerdictRef(
                rule_id=row.rule_id,
                verdict=row.verdict,
                confidence=float(row.confidence),
                band=row.band,
                arithmetic=bool(row.arithmetic),
            )
            for row in rows
        ],
        "trace": [
            NodeTrace(
                node="match",
                duration_ms=_elapsed_ms(started),
                model_calls=(summary or {}).get("model_calls", 0),
                model_role="mid",
                parallel_with=["risk_score"],
            )
        ],
    }


async def risk_score(state: BidState) -> dict:
    """The RiskScorer: deterministic, and it never sees a model.

    Safe to run beside the Matcher because it reads rules, not verdicts.
    """
    from app.services import checking

    started = time.monotonic()
    await checking.score_risks_for_tender(state.org_id, state.tender_id)

    async with org_scoped_session(state.org_id) as session:
        rows = (
            await session.execute(
                select(RiskRow).where(RiskRow.tender_id == state.tender_id)
            )
        ).scalars().all()

    return {
        "risks": [
            RiskRef(
                code=row.code,
                severity=row.severity,
                rupee_impact=float(row.rupee_impact) if row.rupee_impact else None,
                el_id=row.el_id,
            )
            for row in rows
        ],
        "trace": [
            NodeTrace(
                node="risk_score",
                duration_ms=_elapsed_ms(started),
                parallel_with=["match"],
            )
        ],
    }


async def decide(state: BidState) -> dict:
    """The Decider: rupees, computed by code.

    No gateway is constructed here and none is passed. Golden rule 3 and SPEC
    §9 rule 2 both forbid a model producing a money figure, and the cheapest
    way to keep that true is for this node to have nothing to call.
    """
    started = time.monotonic()
    return {
        "trace": [NodeTrace(node="decide", duration_ms=_elapsed_ms(started))],
    }


def gate_4(state: BidState) -> dict:
    """Checkpoint 4 — the bid/no-bid decision. A human signs it off.

    `interrupt()` halts the graph here. There is no branch that skips it and no
    confidence high enough to pass it: SPEC §7 says checkpoints 4–6 never
    auto-pass, so this node has exactly one outgoing edge and it goes to END.
    """
    interrupt(
        {
            "checkpoint": 4,
            "tender_id": str(state.tender_id),
            "awaiting": "a named human must sign off the bid decision",
        }
    )
    return {
        "paused_at": 4,
        "gates": {
            4: Gate(
                number=4,
                auto_passable=False,
                status="waiting",
                reason="the bid decision is a human's to make",
            )
        },
    }
