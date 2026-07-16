"""Tenders router stub. US-03 (manual upload + parser ladder) builds on this;
for now it proves the org-scoped read path end to end."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_org_session
from app.models import Tender

router = APIRouter()


class TenderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    source: str
    created_at: datetime


@router.get("/tenders", response_model=list[TenderOut])
async def list_tenders(session: AsyncSession = Depends(get_org_session)) -> list[TenderOut]:
    result = await session.execute(select(Tender).order_by(Tender.created_at.desc()))
    return [TenderOut.model_validate(t) for t in result.scalars()]
