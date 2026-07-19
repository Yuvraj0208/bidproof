"""Triage service (US-02): build tender signals, load the org's profile
(config, SPEC §15), run the deterministic scorer, persist the result.
Runs automatically after every successful parse and on demand."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from bidproof_triage import (
    Category,
    OrgProfile as TriageProfile,
    TenderSignals,
    Thresholds,
    extract_value_inr,
    triage as run_triage,
)

from app.core.config import get_settings
from app.core.db import org_scoped_session
from app.models import Document, Element, OrgProfile, Tender

logger = logging.getLogger(__name__)

RESOLVABLE_LISTS = {"in_our_lane", "opportunity_radar"}


def _profile_from_row(row: OrgProfile | None) -> TriageProfile:
    settings = get_settings()
    default_weights = {
        "category": settings.fit_w_category,
        "eligibility": settings.fit_w_eligibility,
        "value": settings.fit_w_value,
        "location": settings.fit_w_location,
        "win_history": settings.fit_w_win_history,
    }
    if row is None:
        # No profile yet (onboarding wizard is US-17): no categories are
        # known, so triage will abstain to the human queue — never guess.
        return TriageProfile(weights=default_weights)

    band = row.value_band_inr or {}
    return TriageProfile(
        categories=tuple(
            Category(c["name"], tuple(c.get("keywords", [])))
            for c in (row.categories or [])
        ),
        weights={**default_weights, **(row.weights or {})},
        value_band_inr=(band.get("min_inr"), band.get("max_inr")),
        locations=tuple(row.locations or []),
        win_categories=tuple(row.win_categories or []),
    )


def _thresholds() -> Thresholds:
    settings = get_settings()
    return Thresholds(
        in_lane=settings.triage_in_lane_threshold,
        radar=settings.triage_radar_threshold,
        confidence_floor=settings.triage_confidence_floor,
        borderline_margin=settings.triage_borderline_margin,
    )


async def triage_tender(org_id: uuid.UUID, tender_id: uuid.UUID) -> dict | None:
    async with org_scoped_session(org_id) as session:
        tender = await session.get(Tender, tender_id)
        if tender is None:
            return None

        profile_row = await session.get(OrgProfile, org_id)

        document = (
            await session.execute(
                select(Document.id).where(Document.tender_id == tender_id)
            )
        ).scalar_one_or_none()
        text = ""
        if document is not None:
            rows = (
                await session.execute(
                    select(Element.text)
                    .where(Element.document_id == document)
                    .order_by(Element.page_no, Element.seq)
                    .limit(60)
                )
            ).scalars()
            text = " ".join(rows)

        haystack = f"{tender.title} {text}"
        signals = TenderSignals(
            title=tender.title,
            text=text,
            value_inr=extract_value_inr(haystack),
            closing_at=tender.closing_at,
            now=datetime.now(timezone.utc),
        )
        result = run_triage(signals, _profile_from_row(profile_row), _thresholds())

        tender.radar_list = result.radar_list
        tender.fit_score = result.fit_score
        tender.triage = {
            "components": result.components,
            "matched_category": result.matched_category,
            "reasons": result.reasons,
            "confidence": result.confidence,
            "band": result.band,
            "checkpoint0": result.checkpoint0,
            "resolution": None,
        }
        return tender.triage | {
            "radar_list": result.radar_list,
            "fit_score": result.fit_score,
        }


async def triage_after_parse(org_id: uuid.UUID, tender_id: uuid.UUID) -> None:
    """Post-parse hook: triage must never take ingestion down."""
    try:
        await triage_tender(org_id, tender_id)
    except Exception:
        logger.exception("triage failed for tender %s", tender_id)


async def resolve_triage(
    org_id: uuid.UUID, tender_id: uuid.UUID, new_list: str, reason: str
) -> dict | None:
    """Checkpoint 0: the human confirms the list. The resolution and its
    reason are kept on the tender (append-only audit log arrives in US-16)."""
    async with org_scoped_session(org_id) as session:
        tender = await session.get(Tender, tender_id)
        if tender is None:
            return None
        triage_state = dict(tender.triage or {})
        triage_state["checkpoint0"] = "confirmed"
        triage_state["resolution"] = {
            "list": new_list,
            "reason": reason,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        tender.radar_list = new_list
        tender.triage = triage_state
        return triage_state
