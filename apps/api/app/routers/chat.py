"""Ask BidProof endpoints (US-15): a scoped, cited chat inside each tender
workspace. Answers only from this tender's elements; refuses out of scope."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.tenancy import require_org_id
from app.services import chat

router = APIRouter()


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


@router.post("/tenders/{tender_id}/chat")
async def ask(
    tender_id: uuid.UUID,
    body: AskIn,
    org_id: uuid.UUID = Depends(require_org_id),
    gateway=Depends(chat.get_chat_gateway),
) -> dict:
    result = await chat.ask(org_id, tender_id, body.question, gateway=gateway)
    if result is None:
        raise HTTPException(404, "tender not found")
    return result


@router.get("/tenders/{tender_id}/chat")
async def history(
    tender_id: uuid.UUID, org_id: uuid.UUID = Depends(require_org_id)
) -> list[dict]:
    return await chat.history(org_id, tender_id)
