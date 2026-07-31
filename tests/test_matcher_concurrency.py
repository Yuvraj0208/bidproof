"""The cited judge runs prose rules concurrently, under a bound.

Two properties, and they pull against each other:

* **Concurrency.** A real tender carries dozens of prose rules. Judged one at a
  time at a couple of seconds each, checking takes minutes — long enough that a
  person stops trusting the button. The rules are independent, so they should
  overlap.
* **A bound.** Unbounded `gather` over 60 rules opens 60 simultaneous model
  calls. Hosted free tiers answer that with 429s, and on Windows the selector
  event loop caps at 512 sockets. So the fan-out is capped by
  `LLM_MAX_CONCURRENCY`, not left to the tender's size.

Arithmetic still runs first and never reaches a model — that ordering is the
part of this file most worth protecting, so it is asserted directly rather than
assumed.
"""

import asyncio
import time

from bidproof_matcher import CheckRule, ProductRef

from app.services import checking

# The judge is only consulted when retrieval finds a candidate product — with
# an empty catalogue `_judge` returns needs_human without ever calling the
# gateway, and a timing test built on that would pass whether the code ran
# concurrently or not. So these tests carry a catalogue that genuinely matches,
# and every one of them asserts the gateway was actually reached.
CATALOGUE = [
    ProductRef(
        id="p-1",
        product_code="CP-100",
        product_name="Centrifugal Pump",
        standards=("IS 1520",),
        lead_time_days=30,
        specs={"duty": "continuous"},
    )
]


def prose_rule(n: int) -> CheckRule:
    """A rule arithmetic cannot settle, so it must reach the judge."""
    return CheckRule(
        rule_id=f"r{n}",
        family="technical",
        key=f"spec_{n}",
        requirement_text=f"Pump {n} shall be suitable for continuous duty",
        value_text=None,
        el_id=f"el-{n}",
    )


class SlowGateway:
    """A judge that takes a fixed time to answer, so overlap is measurable."""

    def __init__(self, delay: float = 0.1) -> None:
        self.delay = delay
        self.calls = 0
        self.in_flight = 0
        self.peak_in_flight = 0

    async def complete(self, role, messages, **params):
        self.calls += 1
        self.in_flight += 1
        self.peak_in_flight = max(self.peak_in_flight, self.in_flight)
        try:
            await asyncio.sleep(self.delay)
        finally:
            self.in_flight -= 1
        # Deliberately uncited: the response is voided to NEEDS_HUMAN by
        # validate_judge_citations. This test is about scheduling, and a
        # verdict that passes validation would make it about two things.
        return {"choices": [{"message": {"content": "{}"}}]}


async def test_prose_rules_are_judged_concurrently(monkeypatch):
    """Twelve rules at 0.1s each must not take 1.2s."""
    monkeypatch.setattr(checking, "_max_concurrency", lambda: 6)
    rules = [prose_rule(i) for i in range(12)]
    gateway = SlowGateway(delay=0.1)

    started = time.monotonic()
    results, model_calls = await checking._verdicts_for(
        rules, [], CATALOGUE, gateway, __import__("datetime").date.today()
    )
    elapsed = time.monotonic() - started

    assert len(results) == 12
    # Without this the timing assertion below is meaningless: no gateway call
    # means no sleep, and the test would pass on serial code.
    assert gateway.calls == 12, f"the judge was reached {gateway.calls}/12 times"
    assert model_calls == 12
    # Serial would be ~1.2s; at a bound of 6 the floor is ~0.2s. The ceiling is
    # generous so a slow machine does not make this flaky, but 1.2s is far out.
    assert elapsed < 0.8, (
        f"prose rules still look serial: {elapsed:.2f}s for 12 rules at 0.1s each"
    )


async def test_concurrency_never_exceeds_the_bound(monkeypatch):
    """The cap is what keeps a large tender from tripping rate limits."""
    monkeypatch.setattr(checking, "_max_concurrency", lambda: 4)
    rules = [prose_rule(i) for i in range(20)]
    gateway = SlowGateway(delay=0.05)

    await checking._verdicts_for(
        rules, [], CATALOGUE, gateway, __import__("datetime").date.today()
    )

    assert gateway.calls == 20, f"the judge was reached {gateway.calls}/20 times"
    assert gateway.peak_in_flight > 1, "no overlap at all — this is still serial"
    assert gateway.peak_in_flight <= 4, (
        f"{gateway.peak_in_flight} judge calls were in flight at once, over the "
        "bound of 4 — a 60-rule tender would open 60 connections"
    )


async def test_results_keep_their_rule_order(monkeypatch):
    """Concurrency must not reorder verdicts.

    The Compliance Matrix pairs each rule with its verdict positionally in
    several places; a shuffled list would attach the wrong verdict to the wrong
    rule, which is worse than being slow.
    """
    monkeypatch.setattr(checking, "_max_concurrency", lambda: 8)
    rules = [prose_rule(i) for i in range(10)]

    class Jittery(SlowGateway):
        async def complete(self, role, messages, **params):
            # Later rules answer sooner, so completion order != submission order.
            await asyncio.sleep(0.01 * (10 - self.calls % 10))
            return await super().complete(role, messages, **params)

    jittery = Jittery(delay=0.0)
    results, _ = await checking._verdicts_for(
        rules, [], CATALOGUE, jittery, __import__("datetime").date.today()
    )

    assert jittery.calls == 10, f"the judge was reached {jittery.calls}/10 times"
    assert [r.key for r, _ in results] == [f"spec_{i}" for i in range(10)]


async def test_arithmetic_rules_never_reach_the_gateway():
    """Golden rule 3: numbers are settled by code, before any model is asked."""
    from test_matcher import TURNOVER_FACTS

    numeric = CheckRule(
        rule_id="r-turnover",
        family="financial",
        key="min_turnover",
        requirement_text="Minimum average annual turnover of Rs 5 crore",
        value_text="Rs 5 crore",
        el_id="el-1",
    )
    facts = TURNOVER_FACTS

    class Exploding:
        async def complete(self, *a, **k):
            raise AssertionError("an arithmetic rule reached the model")

    results, model_calls = await checking._verdicts_for(
        [numeric], facts, [], Exploding(), __import__("datetime").date.today()
    )

    assert model_calls == 0
    assert len(results) == 1
