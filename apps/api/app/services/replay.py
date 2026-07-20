"""Replay (US-12, SPEC §13): re-execute a past tender from its stored PDF —
"why did it say COMPLIES three weeks ago?" gets an answer, not a shrug.

Replay rebuilds the derived truth (pages, elements, rules, verdicts, risks)
from the same raw input with the currently pinned configuration; every step
is recorded again under the same trace id."""

import asyncio
import logging
import uuid

from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.db import org_scoped_session
from app.models import Document, Page, ParseRun
from app.observability import get_parse_logger
from app.parsing import get_ladder
from app.services import checking, extraction, ingest
from app.services import triage as triage_service
from app.storage import ObjectStorage

logger = logging.getLogger(__name__)


async def replay_tender(org_id: uuid.UUID, tender_id: uuid.UUID) -> dict | None:
    async with org_scoped_session(org_id) as session:
        document = (
            await session.execute(
                select(Document).where(Document.tender_id == tender_id)
            )
        ).scalar_one_or_none()
        if document is None:
            return None
        document_id, object_key = document.id, document.object_key

    storage = ObjectStorage(get_settings())
    pdf_bytes = await asyncio.to_thread(storage.get_pdf, object_key)

    async with org_scoped_session(org_id) as session:
        # Derived truth is rebuilt from the raw input; deleting pages cascades
        # elements -> rules -> verdicts, exactly the chain being re-derived.
        await session.execute(delete(Page).where(Page.document_id == document_id))
        run = ParseRun(org_id=org_id, document_id=document_id, status="pending",
                       trace_id=tender_id.hex)
        session.add(run)
        await session.flush()
        parse_run_id = run.id

    await ingest.execute_parse_run(
        org_id=org_id, tender_id=tender_id, document_id=document_id,
        parse_run_id=parse_run_id, pdf_bytes=pdf_bytes,
        ladder=get_ladder(), parse_logger=get_parse_logger(),
    )
    await triage_service.triage_after_parse(org_id, tender_id)
    await extraction.extract_after_parse(org_id, tender_id)
    await checking.check_after_extract(org_id, tender_id)
    return {"replayed": True, "tender_id": str(tender_id)}
