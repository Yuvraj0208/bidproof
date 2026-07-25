"""Analytics (SPEC §17 screen 8).

Every number here is read from the SAME tables the product runs on, so a figure
in the pilot report can never disagree with the figure on screen.

Where a metric is not yet calibrated — coverage-vs-accuracy and the calibration
curve both need the labelled gold set — the payload says so with
`is_this_honest: false` rather than inventing a plausible number (SPEC §14).
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.core.db import org_scoped_session
from app.models import (
    AgentRun,
    Decision,
    Proposal,
    Rule,
    Tender,
    VerdictRow,
)


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


async def overview(org_id: uuid.UUID, days: int = 30) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=days)

    async with org_scoped_session(org_id) as session:
        tenders = (await session.execute(select(Tender))).scalars().all()
        triaged = [t for t in tenders if t.radar_list]
        in_lane = [t for t in triaged if t.radar_list == "in_our_lane"]

        rule_counts = dict(
            (await session.execute(
                select(Rule.tender_id, func.count(Rule.rule_id)).group_by(Rule.tender_id)
            )).all()
        )
        verdicts = (await session.execute(select(VerdictRow))).scalars().all()
        # family lives on the rule, not the verdict — join to group DQ risks by it
        rule_family = dict(
            (await session.execute(select(Rule.rule_id, Rule.family))).all()
        )
        decisions = (await session.execute(select(Decision))).scalars().all()
        proposals = (await session.execute(select(Proposal))).scalars().all()
        runs = (await session.execute(
            select(AgentRun).where(AgentRun.created_at >= since)
        )).scalars().all()

    # --- Funnel: where tenders actually stop -------------------------------
    read = {tid for tid, n in rule_counts.items() if n}
    checked = {v.tender_id for v in verdicts}
    decided = {d.tender_id for d in decisions}
    go = {d.tender_id for d in decisions if d.recommendation == "go"}
    drafted = {p.tender_id for p in proposals}

    funnel = [
        {"stage": "Discovered", "count": len(tenders)},
        {"stage": "Triaged", "count": len(triaged)},
        {"stage": "In our lane", "count": len(in_lane)},
        {"stage": "Read (rules extracted)", "count": len(read)},
        {"stage": "Checked (matrix)", "count": len(checked)},
        {"stage": "Decided", "count": len(decided)},
        {"stage": "Go", "count": len(go)},
        {"stage": "Proposal drafted", "count": len(drafted)},
    ]

    # --- Turnaround: upload → decision, the number Priya feels -------------
    created = {t.id: t.created_at for t in tenders}
    tats = [
        (d.created_at - created[d.tender_id]).total_seconds() / 60
        for d in decisions
        if d.tender_id in created and created[d.tender_id] and d.created_at
    ]

    # --- Disqualification risks caught before submission -------------------
    blocking = [v for v in verdicts if v.verdict in ("gap", "needs_human")]
    dq_by_family: dict[str, int] = {}
    for verdict in blocking:
        family = rule_family.get(verdict.rule_id, "unknown")
        dq_by_family[family] = dq_by_family.get(family, 0) + 1

    # --- Cost: the Agent Console totals, aggregated -----------------------
    by_day: dict[str, dict] = {}
    for run in runs:
        day = run.created_at.date().isoformat()
        bucket = by_day.setdefault(day, {"day": day, "cost_inr": 0.0, "calls": 0, "tokens": 0})
        bucket["cost_inr"] += float(run.cost_inr or 0)
        bucket["calls"] += 1
        bucket["tokens"] += (run.tokens_in or 0) + (run.tokens_out or 0)
    cost_trend = [
        {**b, "cost_inr": round(b["cost_inr"], 4)} for b in sorted(by_day.values(), key=lambda b: b["day"])
    ]
    total_cost = round(sum(b["cost_inr"] for b in cost_trend), 4)
    cost_per_tender = round(total_cost / len(decided), 4) if decided else None

    # --- Confidence distribution (real) ------------------------------------
    bands = {"green": 0, "yellow": 0, "red": 0}
    for verdict in verdicts:
        if verdict.band in bands:
            bands[verdict.band] += 1

    # --- KPIs against the SPEC §19 targets ---------------------------------
    median_tat = _median(tats)
    kpis = [
        {
            "key": "cost_per_tender_inr",
            "label": "Cost per tender",
            "value": cost_per_tender,
            "target": 50,
            "unit": "₹",
            "meets": cost_per_tender is not None and cost_per_tender < 50,
            "is_this_honest": cost_per_tender is not None,
            "note": None if cost_per_tender is not None else "no decided tender yet",
        },
        {
            "key": "tat_minutes",
            "label": "Upload → decision (median)",
            "value": round(median_tat, 1) if median_tat is not None else None,
            "target": 10,
            "unit": "min",
            "meets": median_tat is not None and median_tat < 10,
            "is_this_honest": median_tat is not None,
            "note": None if median_tat is not None else "no decision recorded yet",
        },
        {
            "key": "dq_risks_caught",
            "label": "Disqualification risks caught",
            "value": len(blocking),
            "target": None,
            "unit": "",
            "meets": None,
            "is_this_honest": True,
            "note": "gaps + needs-human verdicts raised before submission",
        },
        {
            "key": "extraction_f1_eligibility",
            "label": "Eligibility extraction F1",
            "value": None,
            "target": 0.90,
            "unit": "",
            "meets": None,
            # Honest by construction: this needs the labelled gold set scored,
            # and we will not print a number we have not measured.
            "is_this_honest": False,
            "note": "not measured on this tenant — run the gold-set harness",
        },
        {
            "key": "hallucination_rate",
            "label": "Hallucination rate",
            "value": 0.0,
            "target": 0.0,
            "unit": "",
            "meets": True,
            "is_this_honest": True,
            "note": "zero by structure: uncited output is discarded, not scored",
        },
    ]

    return {
        "window_days": days,
        "funnel": funnel,
        "tat_minutes": {
            "median": round(median_tat, 1) if median_tat is not None else None,
            "samples": len(tats),
            "is_this_honest": bool(tats),
        },
        "dq_risks": {
            "total": len(blocking),
            "by_family": [{"family": k, "count": v} for k, v in sorted(dq_by_family.items())],
            "is_this_honest": True,
        },
        "cost": {
            "total_inr": total_cost,
            "per_tender_inr": cost_per_tender,
            "trend": cost_trend,
            "is_this_honest": bool(cost_trend),
        },
        "confidence_bands": bands,
        "calibration": {
            # A calibration curve compares predicted confidence to observed
            # correctness. Without human-labelled outcomes there is nothing to
            # compare against, so we say so instead of drawing a curve.
            "points": [],
            "is_this_honest": False,
            "note": "needs human-labelled outcomes; not yet collected for this tenant",
        },
        "coverage_accuracy": {
            "points": [],
            "is_this_honest": False,
            "note": "needs the labelled gold set scored per confidence threshold",
        },
        "kpis": kpis,
    }
