"""Pre-bid question pack endpoints (US-08): generate the drafts and read
them. There is deliberately NO send endpoint — the QuestionWriter drafts
only; a human sends every letter (SPEC §5.8, §10)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.core.db import org_scoped_session
from app.core.tenancy import require_org_id
from app.models import QueryLetter
from app.services import questions

router = APIRouter()


class LetterOut(BaseModel):
    id: uuid.UUID
    rule_id: uuid.UUID
    rule_key: str
    el_id: uuid.UUID
    page_no: int
    subject: str
    body: str
    query_deadline: date | None
    status: str


@router.post("/tenders/{tender_id}/questions")
async def generate(
    tender_id: uuid.UUID,
    org_id: uuid.UUID = Depends(require_org_id),
    gateway=Depends(questions.get_question_gateway),
) -> dict:
    result = await questions.generate_questions(org_id, tender_id, gateway=gateway)
    if result is None:
        raise HTTPException(404, "tender not found")
    return result


@router.get("/tenders/{tender_id}/questions", response_model=list[LetterOut])
async def list_questions(
    tender_id: uuid.UUID, org_id: uuid.UUID = Depends(require_org_id)
) -> list[LetterOut]:
    async with org_scoped_session(org_id) as session:
        rows = (
            await session.execute(
                select(QueryLetter)
                .where(QueryLetter.tender_id == tender_id)
                .order_by(QueryLetter.rule_key)
            )
        ).scalars()
        return [
            LetterOut(
                id=letter.id, rule_id=letter.rule_id, rule_key=letter.rule_key,
                el_id=letter.el_id, page_no=letter.page_no, subject=letter.subject,
                body=letter.body, query_deadline=letter.query_deadline,
                status=letter.status,
            )
            for letter in rows
        ]
