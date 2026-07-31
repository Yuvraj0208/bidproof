"""The /process route must hand the checking service a gateway.

This is the wiring behind a bug that looked like caution. `checking._judge`
opens with:

    if gateway is None or not candidates:
        return VerdictResult(Verdict.NEEDS_HUMAN,
            "no judge available or no candidate products — a human decides", ...)

so a route that omits `gateway=` does not fail — it quietly returns
`needs_human` for every prose rule, with a message that reads like a
considered decision. The Compliance Matrix fills with rules awaiting a human
and the cited-judge layer never runs at all.

`checks.recheck` and `checking.check_after_extract` both pass the gateway.
`/process` — the "Process with AI" button, the main path — did not.

Wiring only, so no database and no model: the route's collaborators are
stubbed and we assert what it hands them.
"""

import uuid

import pytest

from app.core.roles import Role
from app.routers import tenders as tenders_router


class _Session:
    """Enough session for the route: an existence check and an audit insert."""

    def __init__(self) -> None:
        self.added: list = []

    async def get(self, _model, _ident):
        return object()  # the tender exists

    def add(self, row) -> None:
        self.added.append(row)


class _Scope:
    def __init__(self, session: _Session) -> None:
        self._session = session

    async def __aenter__(self) -> _Session:
        return self._session

    async def __aexit__(self, *_exc) -> bool:
        return False


@pytest.fixture
def route(monkeypatch):
    """The route with its collaborators replaced by spies."""
    session = _Session()
    monkeypatch.setattr(
        tenders_router, "org_scoped_session", lambda _org_id: _Scope(session)
    )

    async def fake_extract(_org_id, _tender_id, gateway=None):
        return {"rules": 3}

    monkeypatch.setattr(
        tenders_router.extraction_service, "extract_rules", fake_extract
    )

    seen: dict = {}

    async def spy_run_checks(_org_id, _tender_id, gateway=None):
        seen["gateway"] = gateway
        seen["called"] = True
        return {"verdicts": {"complies": 2}, "model_calls": 2}

    monkeypatch.setattr(tenders_router.checking_service, "run_checks", spy_run_checks)

    # Sequential by default, so the gateway assertions below are about the
    # path they name. The conductor tests turn it back on explicitly.
    import app.conductor as conductor

    monkeypatch.setattr(conductor, "conductor_available", lambda: False)
    return seen


async def test_process_hands_checking_a_gateway(route):
    """Without this the cited judge cannot run, whatever the tender says."""
    sentinel = object()

    await tenders_router.process_tender(
        tender_id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        role=Role.BID_EXECUTIVE,
        gateway=sentinel,
    )

    assert route["called"], "checking was never invoked"
    assert route["gateway"] is sentinel, (
        "/process called run_checks without a gateway, so _judge short-circuits "
        "to 'no judge available' and every prose rule falls to needs_human"
    )


async def test_process_runs_through_the_conductor_when_enabled(route, monkeypatch):
    """The graph is the orchestration, and the response says so.

    `orchestrator` is reported rather than assumed: a demo must never be able
    to claim the Conductor ran when it quietly did not.
    """
    calls: dict = {}
    sentinel = object()

    async def fake_run_tender(org_id, tender_id, gateway=None):
        calls["ran"] = True
        # The graph must receive the request's gateway, not build its own —
        # otherwise a stubbed gateway is silently ignored and the test suite
        # puts real calls on the wire.
        calls["gateway"] = gateway
        return {
            "verdict_counts": {"complies": 3, "gap": 1},
            "model_calls": 4,
            "paused_at": 4,
        }

    import app.conductor as conductor

    monkeypatch.setattr(conductor, "run_tender", fake_run_tender)
    monkeypatch.setattr(conductor, "conductor_available", lambda: True)

    out = await tenders_router.process_tender(
        tender_id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        role=Role.BID_EXECUTIVE,
        gateway=sentinel,
    )

    assert calls.get("ran"), "the conductor was not used"
    assert calls["gateway"] is sentinel, "the graph built its own gateway"
    assert out.orchestrator == "conductor"
    assert out.verdicts == {"complies": 3, "gap": 1}
    assert out.model_calls == 4
    # A healthy run STOPS at the human checkpoint. Reaching the end without
    # one would be the bug, not the success.
    assert out.paused_at == 4


async def test_process_falls_back_when_the_graph_fails(route, monkeypatch):
    """Checking must still happen if the graph breaks.

    The fallback is a real one — the same service functions run, just in
    sequence — so a failed graph costs the run its parallelism, not its result.
    """
    async def exploding_run_tender(org_id, tender_id, gateway=None):
        raise RuntimeError("graph blew up")

    import app.conductor as conductor

    monkeypatch.setattr(conductor, "run_tender", exploding_run_tender)
    monkeypatch.setattr(conductor, "conductor_available", lambda: True)

    out = await tenders_router.process_tender(
        tender_id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        role=Role.BID_EXECUTIVE,
        gateway=object(),
    )

    assert out.orchestrator == "sequential"
    assert route["called"], "the sequential path did not run either"
    assert out.verdicts == {"complies": 2}


async def test_process_reports_the_model_calls_checking_made(route):
    """`model_calls` is the Agent Console's spend line for this run.

    It is read straight off the checking summary, so a missing gateway made it
    permanently 0 — the run looked free because it did nothing.
    """
    out = await tenders_router.process_tender(
        tender_id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        role=Role.BID_EXECUTIVE,
        gateway=object(),
    )

    assert out.model_calls == 2
    assert out.verdicts == {"complies": 2}
