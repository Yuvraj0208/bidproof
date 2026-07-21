"""Submission checklist (US-18, SPEC §7 Checkpoint 6).

Every required document is listed. The system checks the uploaded file's
format and whether it is signed; a human ticks each item; and nothing is
submit-ready until every required item is ticked. Checkpoint 6 never
auto-passes.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.db import org_scoped_session
from app.models import Rule, SubmissionItem, Tender

# The standard mandatory documents for a government bid. Tender-specific
# documents are added from parsed submission requirements as those patterns
# mature (deferred, not faked).
STANDARD_ITEMS = [
    {"name": "Technical Bid", "required_format": "pdf", "signature_required": True},
    {"name": "Price Bid / BOQ", "required_format": "pdf", "signature_required": True},
    {"name": "EMD proof or exemption", "required_format": "pdf",
     "signature_required": False},
    {"name": "Signed bidder declarations", "required_format": "pdf",
     "signature_required": True},
]


def _checks_pass(item: SubmissionItem) -> tuple[bool, str | None]:
    """The system's checks: a file of the right format, signed if required."""
    if item.uploaded_format is None:
        return False, "no file attached yet"
    if item.uploaded_format.lower() != item.required_format.lower():
        return False, (
            f"format is {item.uploaded_format!r}, but {item.required_format!r} "
            "is required"
        )
    if item.signature_required and not item.signature_present:
        return False, "the document is not signed"
    return True, None


def _serialise(item: SubmissionItem) -> dict:
    ok, reason = _checks_pass(item)
    return {
        "id": str(item.id), "name": item.name, "required": item.required,
        "required_format": item.required_format,
        "signature_required": item.signature_required,
        "uploaded_format": item.uploaded_format,
        "signature_present": item.signature_present,
        "checks_pass": ok, "checks_reason": reason,
        "ticked": item.ticked, "ticked_by": item.ticked_by,
    }


async def generate_checklist(org_id: uuid.UUID, tender_id: uuid.UUID) -> dict | None:
    async with org_scoped_session(org_id) as session:
        tender = await session.get(Tender, tender_id)
        if tender is None:
            return None
        existing = (
            await session.execute(
                select(SubmissionItem.name).where(
                    SubmissionItem.tender_id == tender_id
                )
            )
        ).scalars().all()
        have = set(existing)
        for spec in STANDARD_ITEMS:
            if spec["name"] not in have:
                session.add(SubmissionItem(
                    org_id=org_id, tender_id=tender_id, required=True, **spec
                ))
    return await read_checklist(org_id, tender_id)


async def read_checklist(org_id: uuid.UUID, tender_id: uuid.UUID) -> dict | None:
    async with org_scoped_session(org_id) as session:
        tender = await session.get(Tender, tender_id)
        if tender is None:
            return None
        items = (
            await session.execute(
                select(SubmissionItem)
                .where(SubmissionItem.tender_id == tender_id)
                .order_by(SubmissionItem.created_at)
            )
        ).scalars().all()
    serialised = [_serialise(i) for i in items]
    required = [i for i in items if i.required]
    submit_ready = len(required) > 0 and all(i.ticked for i in required)
    return {
        "items": serialised,
        "required_count": len(required),
        "ticked_count": sum(1 for i in required if i.ticked),
        "submit_ready": submit_ready,
    }


async def attach_file(
    org_id: uuid.UUID, item_id: uuid.UUID, uploaded_format: str, signed: bool
) -> dict | None:
    """Record an uploaded file against an item; the system re-checks it.
    Attaching always un-ticks — a human must re-tick after any change."""
    async with org_scoped_session(org_id) as session:
        item = await session.get(SubmissionItem, item_id)
        if item is None or item.org_id != org_id:
            return None
        item.uploaded_format = uploaded_format.lower().lstrip(".")
        item.signature_present = signed
        item.ticked = False
        item.ticked_by = None
        item.ticked_at = None
        await session.flush()
        return _serialise(item)


async def tick_item(
    org_id: uuid.UUID, item_id: uuid.UUID, name: str
) -> tuple[dict | None, str | None]:
    """A human ticks one item — only if the system's format + signature
    checks pass. Returns (item, error)."""
    async with org_scoped_session(org_id) as session:
        item = await session.get(SubmissionItem, item_id)
        if item is None or item.org_id != org_id:
            return None, None
        ok, reason = _checks_pass(item)
        if not ok:
            return None, f"cannot tick: {reason}"
        item.ticked = True
        item.ticked_by = name
        item.ticked_at = datetime.now(timezone.utc)
        await session.flush()
        return _serialise(item), None
