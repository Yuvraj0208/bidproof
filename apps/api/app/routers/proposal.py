"""Proposal endpoints (US-09): generate after GO, read the draft with its
claim verification, and manage the block library (quarantine by default)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from bidproof_librarian import chop_proposal

from app.core.db import org_scoped_session
from app.core.tenancy import require_org_id
from app.models import LibraryBlockRow, Proposal, ProposalSection
from app.services import proposal as proposal_service

router = APIRouter()


class GenerateIn(BaseModel):
    # The tender's format wins: pass the tender-dictated section list here.
    sections: list[str] | None = None


class SectionOut(BaseModel):
    id: uuid.UUID
    section_tag: str
    position: int
    content: str
    claims: list
    verified_pct: float | None
    dropped_untagged: int
    approved: bool


class ProposalOut(BaseModel):
    id: uuid.UUID
    tender_id: uuid.UUID
    status: str
    format_source: str
    duration_ms: int | None
    sections: list[SectionOut]


class BlockIn(BaseModel):
    section_tag: str = Field(min_length=3)
    text: str = Field(min_length=20)
    outcome: str
    source_name: str = Field(min_length=3)


class ProposalUploadIn(BaseModel):
    text: str = Field(min_length=50)
    outcome: str
    source_name: str = Field(min_length=3)


@router.post("/tenders/{tender_id}/proposal")
async def generate(
    tender_id: uuid.UUID,
    body: GenerateIn | None = None,
    org_id: uuid.UUID = Depends(require_org_id),
    gateway=Depends(proposal_service.get_writer_gateway),
) -> dict:
    try:
        result = await proposal_service.generate_proposal(
            org_id, tender_id, gateway=gateway,
            sections=body.sections if body else None,
        )
    except proposal_service.NoGoDecisionError as error:
        raise HTTPException(409, str(error))
    if result is None:
        raise HTTPException(404, "tender not found")
    return result


@router.get("/tenders/{tender_id}/proposal", response_model=ProposalOut)
async def read(
    tender_id: uuid.UUID, org_id: uuid.UUID = Depends(require_org_id)
) -> ProposalOut:
    async with org_scoped_session(org_id) as session:
        proposal = (
            await session.execute(
                select(Proposal).where(Proposal.tender_id == tender_id)
            )
        ).scalar_one_or_none()
        if proposal is None:
            raise HTTPException(404, "no proposal drafted for this tender")
        sections = (
            await session.execute(
                select(ProposalSection)
                .where(ProposalSection.proposal_id == proposal.id)
                .order_by(ProposalSection.position)
            )
        ).scalars()
        return ProposalOut(
            id=proposal.id, tender_id=proposal.tender_id, status=proposal.status,
            format_source=proposal.format_source, duration_ms=proposal.duration_ms,
            sections=[
                SectionOut(
                    id=s.id, section_tag=s.section_tag, position=s.position,
                    content=s.content, claims=s.claims,
                    verified_pct=s.verified_pct,
                    dropped_untagged=s.dropped_untagged, approved=s.approved,
                )
                for s in sections
            ],
        )


@router.post("/library/blocks", status_code=201)
async def add_block(
    body: BlockIn, org_id: uuid.UUID = Depends(require_org_id)
) -> dict:
    if body.outcome not in ("won", "lost", "synthetic"):
        raise HTTPException(400, "outcome must be won, lost, or synthetic")
    async with org_scoped_session(org_id) as session:
        block = LibraryBlockRow(
            org_id=org_id, section_tag=body.section_tag, text=body.text,
            outcome=body.outcome, source_name=body.source_name,
            quarantined=True,   # §11.3: new blocks sit in quarantine
        )
        session.add(block)
        await session.flush()
        return {"id": str(block.id), "quarantined": True}


@router.post("/library/proposals", status_code=201)
async def upload_proposal(
    body: ProposalUploadIn, org_id: uuid.UUID = Depends(require_org_id)
) -> dict:
    """Chop a past proposal into blocks via the Librarian. All blocks land
    quarantined until a reviewer approves them (roles arrive in US-16)."""
    if body.outcome not in ("won", "lost", "synthetic"):
        raise HTTPException(400, "outcome must be won, lost, or synthetic")
    blocks = chop_proposal(body.text, body.outcome, body.source_name)
    async with org_scoped_session(org_id) as session:
        for block in blocks:
            session.add(LibraryBlockRow(
                org_id=org_id, section_tag=block.section_tag, text=block.text,
                outcome=block.outcome, source_name=block.source_name,
                quarantined=True,
            ))
    return {"blocks": len(blocks), "quarantined": True}


@router.get("/library/blocks")
async def list_blocks(
    include_quarantined: bool = False,
    org_id: uuid.UUID = Depends(require_org_id),
) -> list[dict]:
    async with org_scoped_session(org_id) as session:
        query = select(LibraryBlockRow).order_by(LibraryBlockRow.created_at)
        if not include_quarantined:
            query = query.where(LibraryBlockRow.quarantined.is_(False))
        return [
            {
                "id": str(b.id), "section_tag": b.section_tag, "text": b.text,
                "outcome": b.outcome, "source_name": b.source_name,
                "quarantined": b.quarantined,
            }
            for b in (await session.execute(query)).scalars()
        ]
