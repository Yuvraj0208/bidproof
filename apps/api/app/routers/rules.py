"""Rules endpoints (US-04): extraction trigger, the grounded rules feed
(each row joined to its element's page+box — the click-to-proof payload),
and the raw PDF stream the viewer renders."""

import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import org_scoped_session
from app.core.roles import Role, get_role
from app.core.tenancy import require_org_id
from app.models import Document, Element, Rule
from app.services import extraction, flywheel
from app.storage import ObjectStorage

router = APIRouter()


class BBoxOut(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class LearnedOut(BaseModel):
    """A pre-fill carried across tenders by the correction flywheel (US-20).
    Always shown, never silently applied — the human still approves."""

    suggested_value: str
    note: str
    based_on_count: int
    source_tender_id: uuid.UUID | None


class RuleOut(BaseModel):
    rule_id: uuid.UUID
    family: str
    key: str
    requirement_text: str
    value: str | None
    el_id: uuid.UUID
    document_id: uuid.UUID
    page_no: int
    bbox: BBoxOut
    source: str
    status: str
    confidence: float
    band: str
    reason: str
    learned: LearnedOut | None = None


class CorrectIn(BaseModel):
    corrected_value: str = Field(min_length=1)
    name: str = Field(min_length=1)


@router.post("/tenders/{tender_id}/extract")
async def run_extraction(
    tender_id: uuid.UUID,
    org_id: uuid.UUID = Depends(require_org_id),
    gateway=Depends(extraction.get_extraction_gateway),
) -> dict:
    summary = await extraction.extract_rules(org_id, tender_id, gateway=gateway)
    if summary is None:
        raise HTTPException(404, "tender has no parsed document")
    return summary


@router.get("/tenders/{tender_id}/rules", response_model=list[RuleOut])
async def list_rules(
    tender_id: uuid.UUID, org_id: uuid.UUID = Depends(require_org_id)
) -> list[RuleOut]:
    async with org_scoped_session(org_id) as session:
        rows = (
            await session.execute(
                select(Rule, Element)
                .join(Element, Rule.el_id == Element.el_id)
                .where(Rule.tender_id == tender_id)
                .order_by(Rule.family, Rule.key)
            )
        ).all()
        # Attach any learned pre-fill for these clause keys — the memory the
        # flywheel carries across tenders (US-20). Corrections made on THIS
        # tender are excluded so it never cites itself.
        prefills = await flywheel.prefills_for_keys(
            session,
            org_id,
            [rule.key for rule, _ in rows],
            exclude_tender_id=tender_id,
        )
        return [
            RuleOut(
                rule_id=rule.rule_id,
                family=rule.family,
                key=rule.key,
                requirement_text=rule.requirement_text,
                value=rule.value_text,
                el_id=rule.el_id,
                document_id=element.document_id,
                page_no=element.page_no,
                bbox=BBoxOut(x0=element.x0, y0=element.y0, x1=element.x1, y1=element.y1),
                source=rule.source,
                status=rule.status,
                confidence=rule.confidence,
                band=rule.band,
                reason=rule.reason,
                learned=(
                    LearnedOut(
                        suggested_value=prefills[rule.key].suggested_value,
                        note=prefills[rule.key].note,
                        based_on_count=prefills[rule.key].based_on_count,
                        source_tender_id=prefills[rule.key].source_tender_id,
                    )
                    if rule.key in prefills
                    else None
                ),
            )
            for rule, element in rows
        ]


@router.post("/tenders/{tender_id}/rules/{rule_id}/correct")
async def correct_rule(
    tender_id: uuid.UUID,
    rule_id: uuid.UUID,
    body: CorrectIn,
    org_id: uuid.UUID = Depends(require_org_id),
    role: Role = Depends(get_role),
) -> dict:
    """Record a human's correction of an extracted clause (US-20). Anyone in
    the acting chain (bid_executive and above) may correct; only reviewer+
    corrections become labels that teach future tenders (SPEC §11.3). Viewers
    and the auditor cannot correct at all."""
    if role in (Role.VIEWER, Role.AUDITOR):
        raise HTTPException(
            403, f"role '{role.value}' may not correct a rule"
        )
    async with org_scoped_session(org_id) as session:
        rule = await session.get(Rule, rule_id)
        if rule is None or rule.tender_id != tender_id:
            raise HTTPException(404, "rule not found on this tender")
        # The correction applies to this tender's rule now…
        rule.value_text = body.corrected_value.strip()
        # …and is recorded for the flywheel — a label only if reviewer+.
        correction = await flywheel.record_correction(
            session,
            org_id=org_id,
            tender_id=tender_id,
            key=rule.key,
            family=rule.family,
            corrected_value=body.corrected_value,
            role=role,
            name=body.name,
            rule_id=rule_id,
        )
        return {
            "correction_id": str(correction.id),
            "key": rule.key,
            "is_label": correction.is_label,
            "message": (
                "recorded as a training label — future similar tenders will "
                "pre-fill this"
                if correction.is_label
                else "recorded for this tender only; a reviewer's correction is "
                "required to teach future tenders"
            ),
        }


@router.get("/tenders/{tender_id}/document")
async def get_document(
    tender_id: uuid.UUID, org_id: uuid.UUID = Depends(require_org_id)
) -> Response:
    async with org_scoped_session(org_id) as session:
        document = (
            await session.execute(
                select(Document)
                .where(Document.tender_id == tender_id)
                .order_by(Document.version.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if document is None:
            raise HTTPException(404, "tender has no document")
        object_key = document.object_key

    storage = ObjectStorage(get_settings())
    data = await asyncio.to_thread(storage.get_pdf, object_key)
    return Response(content=data, media_type="application/pdf")


@router.get("/documents/{document_id}/file")
async def get_document_file(
    document_id: uuid.UUID, org_id: uuid.UUID = Depends(require_org_id)
) -> Response:
    """Per-document PDF stream. After an amendment a tender has several
    documents; a rule's proof lives in the document it was extracted from,
    so click-to-proof loads that document by id (US-07)."""
    async with org_scoped_session(org_id) as session:
        document = await session.get(Document, document_id)
        if document is None:
            raise HTTPException(404, "document not found")
        object_key = document.object_key

    storage = ObjectStorage(get_settings())
    data = await asyncio.to_thread(storage.get_pdf, object_key)
    return Response(content=data, media_type="application/pdf")
