"""The evaluation registry: what can be measured, and how.

One place listing every component, so a new evaluator is a line here rather than
a change in the router and the UI. Evaluators are run on demand — several load ML
models or read every gold PDF, so none of this runs on a request path by accident.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from typing import Awaitable, Callable

from app.services.evaluation.pipeline import (
    evaluate_proposals,
    evaluate_retrieval,
    evaluate_rule_extraction,
    evaluate_scraping,
)
from app.services.evaluation.readers import evaluate_ocr, evaluate_text_engines
from app.services.evaluation.types import Evaluation, GroundTruth, Status

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Registered:
    component: str
    # Roughly how long a run takes, so the UI can warn before starting one.
    cost: str  # "fast" | "slow"
    needs_org: bool
    run: Callable[..., Evaluation | Awaitable[Evaluation]]


REGISTRY: tuple[Registered, ...] = (
    Registered("rule_extraction", "fast", False, evaluate_rule_extraction),
    Registered("scraping", "fast", True, evaluate_scraping),
    Registered("proposals", "fast", True, evaluate_proposals),
    Registered("retrieval", "fast", False, evaluate_retrieval),
    # These two load ML models and read real PDFs.
    Registered("ocr", "slow", False, evaluate_ocr),
    Registered("text_engines", "slow", False, evaluate_text_engines),
)

BY_COMPONENT = {r.component: r for r in REGISTRY}


async def run_one(component: str, org_id: uuid.UUID) -> Evaluation:
    """Run a single evaluator. A crash becomes an ERROR result, never a zero —
    an evaluation subsystem that hides its own failures is worse than none."""
    entry = BY_COMPONENT.get(component)
    if entry is None:
        raise KeyError(component)
    try:
        if asyncio.iscoroutinefunction(entry.run):
            return await entry.run(org_id) if entry.needs_org else await entry.run()
        # Sync evaluators can be slow (models, PDFs); keep the loop free.
        return await asyncio.to_thread(
            entry.run, org_id
        ) if entry.needs_org else await asyncio.to_thread(entry.run)
    except Exception as exc:
        logger.exception("evaluator %s failed", component)
        return Evaluation(
            component=component,
            label=component.replace("_", " ").title(),
            what_it_measures="",
            status=Status.ERROR,
            ground_truth=GroundTruth.NONE,
            blocked_reason=f"{type(exc).__name__}: {exc}"[:300],
            how_to_fix="See the API log for the full traceback.",
        )


async def run_all(org_id: uuid.UUID, include_slow: bool = False) -> list[Evaluation]:
    components = [
        r.component for r in REGISTRY if include_slow or r.cost == "fast"
    ]
    return [await run_one(name, org_id) for name in components]


def catalogue() -> list[dict]:
    """What exists, without running anything."""
    return [
        {"component": r.component, "cost": r.cost, "needs_org": r.needs_org}
        for r in REGISTRY
    ]
