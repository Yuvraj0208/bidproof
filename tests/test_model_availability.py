"""The model-availability probe must cost one probe, however many ask.

The badge that tells an operator whether answers came from a model or from a
template is polled by every open tab. Each poll that misses the cache used to
run its own full three-role probe at `max_tokens=1600`, so five tabs meant
fifteen concurrent live calls — load the app inflicted on itself. In the
2026-08-03 session that is exactly what it looked like: five `/health/models`
hits in a row, then `role mid did not answer within 45s` in the middle of a
discovery run that was competing with them.

A probe is a diagnostic. It must never be the reason the thing it diagnoses
looks unhealthy.
"""

import asyncio

import pytest


@pytest.fixture
def availability():
    """The module with its cache cleared, and cleared again afterwards, so a
    probe result cannot leak between tests."""
    from app.llm import availability as module

    def clear():
        module._status = None
        module._probed_at = 0.0

    clear()
    yield module
    clear()


def slow_probe(calls: list[str], delay: float = 0.05):
    """Stands in for three real roles: slow enough that callers overlap."""

    async def probe(timeout_s: float = 45.0) -> dict:
        calls.append("probe")
        await asyncio.sleep(delay)
        return {
            "mode": "live",
            "roles": {r: {"ok": True, "model": f"{r}-model", "error": None}
                      for r in ("mid", "small", "strong")},
            "healthy": ["mid", "small", "strong"],
        }

    return probe


async def test_concurrent_refreshes_probe_the_gateway_once(availability, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(availability, "probe_roles", slow_probe(calls))

    results = await asyncio.gather(*(availability.refresh() for _ in range(5)))

    assert len(calls) == 1, f"five callers ran {len(calls)} probes"
    # Every caller gets the real answer, not a placeholder for having lost a race.
    assert all(r["mode"] == "live" for r in results)
    assert all(r["healthy"] == ["mid", "small", "strong"] for r in results)


async def test_a_caller_arriving_during_a_probe_waits_for_it(availability, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(availability, "probe_roles", slow_probe(calls, delay=0.1))

    first = asyncio.create_task(availability.refresh())
    await asyncio.sleep(0.02)  # mid-probe
    second = await availability.refresh()
    await first

    assert len(calls) == 1
    assert second["mode"] == "live"


async def test_the_cache_still_serves_readers_without_probing(availability, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(availability, "probe_roles", slow_probe(calls))

    await availability.refresh()
    assert availability.cached() is not None
    await availability.refresh()

    assert len(calls) == 1, "a warm cache must not be re-probed"


async def test_an_explicit_recheck_is_still_honoured(availability, monkeypatch):
    """`/health/models?refresh=true` is a human pressing re-check after fixing
    the gateway. Coalescing that onto a stale cached answer would strand the
    badge on bad news the operator has already dealt with."""
    calls: list[str] = []
    monkeypatch.setattr(availability, "probe_roles", slow_probe(calls))

    await availability.refresh()
    await availability.refresh(force=True)

    assert len(calls) == 2


async def test_a_failed_probe_does_not_wedge_the_next_one(availability, monkeypatch):
    """The lock must be released on the error path too, or one unreachable
    gateway would freeze every later check behind it."""
    calls: list[str] = []

    async def broken(timeout_s: float = 45.0) -> dict:
        calls.append("probe")
        raise RuntimeError("RemoteProtocolError: Server disconnected")

    monkeypatch.setattr(availability, "probe_roles", broken)
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await availability.refresh()

    monkeypatch.setattr(availability, "probe_roles", slow_probe(calls))
    assert (await availability.refresh())["mode"] == "live"
    assert len(calls) == 3
