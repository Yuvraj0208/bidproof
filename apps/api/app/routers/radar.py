"""The Tender Radar (US-02): two lists + the Checkpoint-0 human queue.
Every card explains itself and carries {confidence, band, reasons} — the
contract the US-13 confidence chip will render."""

import uuid
from datetime import datetime, timezone

from bidproof_triage import refresh_deadline_reason
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.services import portal_links
from app.core.db import org_scoped_session
from app.core.tenancy import require_org_id
from app.models import Document, ParseRun, Tender
from app.services import triage as triage_service

router = APIRouter()

# `not_relevant` is a real list a caller may ask for, but it is never part of
# the default radar view — that is the whole point of scoring it.
VALID_LISTS = {"in_our_lane", "opportunity_radar", "needs_human", "not_relevant"}
HIDDEN_BY_DEFAULT = {"not_relevant"}


class RadarCard(BaseModel):
    tender_id: uuid.UUID
    title: str
    source: str
    external_id: str | None
    closing_at: datetime | None
    # None while a tender is still being read: triage runs after the parse.
    radar_list: str | None = None
    fit_score: float | None
    confidence: float | None
    band: str | None
    matched_category: str | None
    reasons: list[str]
    checkpoint0: str | None
    # Portal listings carry metadata only — the PDF sits behind a session. The
    # UI needs to know, so it can point at the portal instead of offering a
    # "Process with AI" that can only 409.
    has_document: bool = False
    # A link that still resolves when the human clicks it, plus a line telling
    # them what to do when the portal's own link has expired (portal_links).
    portal_url: str | None = None
    # The manual route, kept separate because on CPPP it costs a captcha — the
    # UI must warn before sending anyone there.
    portal_search_url: str | None = None
    portal_requires_captcha: bool = False
    portal_hint: str | None = None
    # Whether the portal will hand us the PDF directly. GeM will; CPPP will not.
    # Decided here so the UI never has to know one portal from another.
    can_fetch_document: bool = False
    # How the reading of the document went. A tender that is still being parsed,
    # or whose parse failed, has no radar list yet — it must still be visible,
    # or an upload simply disappears.
    parse_status: str | None = None


class ResolveIn(BaseModel):
    list: str
    reason: str


@router.get("/radar", response_model=list[RadarCard])
async def radar(
    list_name: str | None = Query(default=None, alias="list"),
    org_id: uuid.UUID = Depends(require_org_id),
) -> list[RadarCard]:
    if list_name is not None and list_name not in VALID_LISTS:
        raise HTTPException(400, f"list must be one of {sorted(VALID_LISTS)}")

    async with org_scoped_session(org_id) as session:
        # Triaged tenders, filtered to the requested list.
        query = (
            select(Tender)
            .where(Tender.radar_list.is_not(None))
            .order_by(Tender.fit_score.desc().nulls_last())
        )
        if list_name:
            query = query.where(Tender.radar_list == list_name)
        else:
            query = query.where(Tender.radar_list.notin_(HIDDEN_BY_DEFAULT))
        tenders = list((await session.execute(query)).scalars())

        # Plus every tender that has NOT been triaged yet, whatever list was
        # asked for. Triage runs after parsing, in the background, so a fresh
        # upload has no list for as long as the read takes — and a failed parse
        # never gets one at all. Filtering those out made an upload vanish from
        # the product with no trace, which is how a 9-page scan "disappeared".
        untriaged = list(
            (
                await session.execute(
                    select(Tender)
                    .where(Tender.radar_list.is_(None))
                    .order_by(Tender.created_at.desc())
                )
            ).scalars()
        )
        tenders = untriaged + tenders
        ids = [t.id for t in tenders] or [None]
        with_docs = set(
            (
                await session.execute(
                    select(Document.tender_id).where(Document.tender_id.in_(ids))
                )
            ).scalars()
        )

        # The latest parse status per tender, so an untriaged card can say
        # whether it is still being read or could not be read at all.
        parse_status: dict = {}
        for tender_id_, status in (
            await session.execute(
                select(Document.tender_id, ParseRun.status)
                .join(ParseRun, ParseRun.document_id == Document.id)
                .where(Document.tender_id.in_(ids))
                .order_by(ParseRun.created_at.desc())
            )
        ).all():
            parse_status.setdefault(tender_id_, status)

        # One `now` for the whole list, so two cards read at the same moment
        # cannot disagree about what day it is.
        now = datetime.now(timezone.utc)

        return [
            RadarCard(
                tender_id=t.id,
                title=t.title,
                source=t.source,
                external_id=t.external_id,
                closing_at=t.closing_at,
                radar_list=t.radar_list,
                fit_score=t.fit_score,
                confidence=(t.triage or {}).get("confidence"),
                band=(t.triage or {}).get("band"),
                matched_category=(t.triage or {}).get("matched_category"),
                # The deadline phrase is recomputed for today. Re-discovery of a
                # tender already held is a duplicate and returns early, so the
                # stored sentence would otherwise age a day per day while the
                # countdown chip beside it stayed live.
                reasons=refresh_deadline_reason(
                    (t.triage or {}).get("reasons", []), t.closing_at, now
                ),
                checkpoint0=(t.triage or {}).get("checkpoint0"),
                has_document=t.id in with_docs,
                portal_url=portal_links.stable_portal_url(t.source, t.portal_url),
                portal_search_url=portal_links.portal_search_url(t.source),
                portal_requires_captcha=portal_links.requires_captcha(t.source),
                portal_hint=portal_links.portal_hint(
                    t.source, t.external_id, t.portal_url
                ),
                can_fetch_document=(
                    t.id not in with_docs
                    and portal_links.document_url(t.source, t.portal_url) is not None
                ),
                parse_status=parse_status.get(t.id),
            )
            for t in tenders
        ]


@router.post("/tenders/{tender_id}/triage")
async def rerun_triage(
    tender_id: uuid.UUID, org_id: uuid.UUID = Depends(require_org_id)
) -> dict:
    result = await triage_service.triage_tender(org_id, tender_id)
    if result is None:
        raise HTTPException(404, "tender not found")
    return result


@router.post("/tenders/{tender_id}/triage/resolve")
async def resolve(
    tender_id: uuid.UUID,
    body: ResolveIn,
    org_id: uuid.UUID = Depends(require_org_id),
) -> dict:
    if body.list not in triage_service.RESOLVABLE_LISTS:
        raise HTTPException(
            400, f"list must be one of {sorted(triage_service.RESOLVABLE_LISTS)}"
        )
    if not body.reason.strip():
        raise HTTPException(400, "a reason is required to resolve Checkpoint 0")
    result = await triage_service.resolve_triage(
        org_id, tender_id, body.list, body.reason.strip()
    )
    if result is None:
        raise HTTPException(404, "tender not found")
    return result
