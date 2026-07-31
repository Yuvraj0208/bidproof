"""Evaluating the rest of the pipeline: extraction, scraping, proposals, retrieval.

Each evaluator is honest about the kind of ground truth it has, because the kinds
are not equally strong:

* **Rule extraction** has 25 labelled cases — but they are SYNTHETIC, generated
  alongside the extractor's own patterns. Scoring 1.00 against them says the
  extractor still does what it did last week; it says almost nothing about a real
  tender. That is reported as `synthetic`, and the screen must show it that way.
* **Scraping** is scored on field completeness of what actually landed, which is
  derived rather than labelled: nobody wrote down what the portal *should* have
  returned, but "a tender with no closing date is less useful than one with" is
  true regardless.
* **Proposals** are scored by the FactChecker, which is part of the product. Real
  data, but not an independent oracle — a claim it cannot verify may be the
  writer's fault or the capability database's. Reported as `self_reported`.
* **Retrieval** is not implemented, so it reports exactly that instead of a zero.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path

from sqlalchemy import func, select

from app.services.evaluation.types import Evaluation, GroundTruth, Metric, Status

GOLD_DIR = Path(__file__).resolve().parents[5] / "tests" / "gold"


def evaluate_rule_extraction() -> Evaluation:
    """Precision/recall/F1 over the labelled gold set, via the real harness."""
    started = time.monotonic()
    base = Evaluation(
        component="rule_extraction",
        label="Rule extraction",
        what_it_measures=(
            "Whether the extractor finds the rules a labelled tender actually "
            "contains, and whether it invents ones it does not."
        ),
        status=Status.ERROR,
        ground_truth=GroundTruth.SYNTHETIC,
    )
    if not GOLD_DIR.exists():
        base.status = Status.NO_GROUND_TRUTH
        base.blocked_reason = "tests/gold does not exist."
        base.how_to_fix = "Add cases as tests/gold/<id>/{tender.pdf,labels.json}."
        return base

    import sys

    harness_dir = str(GOLD_DIR.parent)
    if harness_dir not in sys.path:
        sys.path.insert(0, harness_dir)
    try:
        from goldset_harness import evaluate as run_goldset
    except Exception as exc:
        base.blocked_reason = f"could not load the gold-set harness: {exc}"[:200]
        return base

    report = run_goldset(GOLD_DIR).to_dict()
    families = report.get("per_family", {})
    cases = report.get("tenders", 0)

    def _avg(field: str) -> float | None:
        values = [f[field] for f in families.values() if f.get(field) is not None]
        return round(sum(values) / len(values), 4) if values else None

    synthetic = any(
        (GOLD_DIR / case / "labels.json").exists()
        and '"synthetic": true' in (GOLD_DIR / case / "labels.json").read_text(
            encoding="utf-8"
        )
        for case in [p.name for p in sorted(GOLD_DIR.glob("gold-*"))][:1]
    )
    base.ground_truth = GroundTruth.SYNTHETIC if synthetic else GroundTruth.HUMAN_LABELLED

    base.status = Status.MEASURED
    base.duration_s = round(time.monotonic() - started, 2)
    base.metrics = [
        Metric("precision", "Precision (mean over families)", _avg("precision"),
               "ratio", sample_size=cases),
        Metric("recall", "Recall (mean over families)", _avg("recall"),
               "ratio", sample_size=cases),
        Metric("f1", "F1 (mean over families)", _avg("f1"), "ratio", sample_size=cases),
        Metric("exact_number_match", "Numbers matched exactly",
               report.get("exact_number_match_rate"), "ratio", sample_size=cases),
        Metric("hallucination_rate", "Rules invented", report.get("hallucination_rate"),
               "ratio", higher_is_better=False, sample_size=cases),
    ]
    if base.ground_truth is GroundTruth.SYNTHETIC:
        base.blocked_reason = (
            "The gold cases are synthetic, generated alongside the extractor's own "
            "patterns, so these scores mostly prove the extractor has not "
            "regressed — not that it reads real tenders well."
        )
        base.how_to_fix = (
            "Replace tests/gold/*/tender.pdf with real tenders and hand-label "
            "labels.json. Ten real cases are worth more than a hundred synthetic."
        )
    return base


async def evaluate_scraping(org_id: uuid.UUID) -> Evaluation:
    """Field completeness of what discovery actually landed, per portal.

    Not "did the scrape succeed" — the discovery report already says that. This
    asks the more useful question: of the tenders we hold, how many are usable?
    A tender with no closing date cannot be prioritised; one with no link cannot
    be opened.
    """
    from app.core.db import org_scoped_session
    from app.models import Document, Tender

    started = time.monotonic()
    base = Evaluation(
        component="scraping",
        label="Portal scraping",
        what_it_measures=(
            "Of the tenders each portal gave us, how many carry the fields that "
            "make one actionable: a reference, a deadline, a link, a document."
        ),
        status=Status.ERROR,
        ground_truth=GroundTruth.DERIVED,
    )

    async with org_scoped_session(org_id) as session:
        rows = (
            await session.execute(
                select(
                    Tender.source,
                    func.count(Tender.id),
                    func.count(Tender.external_id),
                    func.count(Tender.closing_at),
                    func.count(Tender.portal_url),
                ).group_by(Tender.source)
            )
        ).all()
        with_docs = dict(
            (
                await session.execute(
                    select(Tender.source, func.count(func.distinct(Document.tender_id)))
                    .join(Document, Document.tender_id == Tender.id)
                    .group_by(Tender.source)
                )
            ).all()
        )

    if not rows:
        base.status = Status.NO_GROUND_TRUTH
        base.blocked_reason = "No tenders have been discovered yet."
        base.how_to_fix = "Run a scrape from the Tender Radar."
        return base

    metrics: list[Metric] = []
    for source, total, refs, closings, links in sorted(rows):
        docs = with_docs.get(source, 0)
        metrics.append(
            Metric(
                key=f"{source}_completeness",
                label=f"{source}: fields present",
                value=round((refs + closings + links) / (3 * total), 3),
                unit="ratio",
                sample_size=total,
                detail=(
                    f"reference {refs}/{total}, deadline {closings}/{total}, "
                    f"link {links}/{total}, document {docs}/{total}"
                ),
            )
        )
    base.status = Status.MEASURED
    base.duration_s = round(time.monotonic() - started, 2)
    base.metrics = metrics
    return base


async def evaluate_proposals(org_id: uuid.UUID) -> Evaluation:
    """How well generated prose is grounded, over real proposals."""
    from app.core.db import org_scoped_session
    from app.models import ProposalSection

    started = time.monotonic()
    base = Evaluation(
        component="proposals",
        label="Proposal grounding",
        what_it_measures=(
            "Of the factual sentences the writer produced, how many the "
            "FactChecker could tie to real company data — and how many it "
            "found contradicted."
        ),
        status=Status.ERROR,
        ground_truth=GroundTruth.SELF_REPORTED,
    )

    async with org_scoped_session(org_id) as session:
        sections = (
            await session.execute(select(ProposalSection))
        ).scalars().all()

    if not sections:
        base.status = Status.NO_GROUND_TRUTH
        base.blocked_reason = "No proposal sections have been generated yet."
        base.how_to_fix = "Generate a proposal from the Proposal Studio."
        return base

    claims = verified = contradicted = cannot = dropped = 0
    for section in sections:
        for claim in section.claims or []:
            claims += 1
            status = claim.get("status")
            verified += status == "verified"
            contradicted += status == "contradicted"
            cannot += status == "cannot_verify"
        dropped += section.dropped_untagged or 0

    base.status = Status.MEASURED
    base.duration_s = round(time.monotonic() - started, 2)
    base.metrics = [
        Metric("verified_rate", "Claims verified against company data",
               round(verified / claims, 4) if claims else None, "ratio",
               sample_size=claims),
        Metric("contradicted_rate", "Claims contradicted",
               round(contradicted / claims, 4) if claims else None, "ratio",
               higher_is_better=False, sample_size=claims),
        Metric("cannot_verify_rate", "Claims that could not be checked",
               round(cannot / claims, 4) if claims else None, "ratio",
               higher_is_better=False, sample_size=claims,
               detail="usually a gap in the capability database, not a bad sentence"),
        Metric("dropped_untagged", "Sentences dropped for having no source",
               float(dropped), "count", higher_is_better=False,
               sample_size=len(sections),
               detail="the ground-check working: untagged prose never ships"),
    ]
    return base


def evaluate_retrieval() -> Evaluation:
    """Retrieval is not built yet, and says so."""
    return Evaluation(
        component="retrieval",
        label="Retrieval / RAG",
        what_it_measures=(
            "Whether the passages fetched for a question are the ones that "
            "actually answer it — recall@k and mean reciprocal rank."
        ),
        status=Status.NOT_IMPLEMENTED,
        ground_truth=GroundTruth.NONE,
        blocked_reason=(
            "There is no embedding retrieval in the product yet. The Ask "
            "BidProof chat scores elements by keyword overlap, and the "
            "librarian agent has no index. Reporting a retrieval score now "
            "would be measuring something that does not exist."
        ),
        how_to_fix=(
            "When BGE-M3 retrieval lands (SPEC §5.4), add labelled queries as "
            "tests/gold/retrieval.json — question, tender, and the el_ids that "
            "genuinely answer it — and this evaluator computes recall@k and MRR."
        ),
    )
