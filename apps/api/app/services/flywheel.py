"""The correction flywheel (US-20, SPEC §8 layer 4 and §11.3).

Human corrections are recorded per clause key. Only reviewer-or-above
corrections become *labels* — a junior or compromised account cannot quietly
teach the system wrong answers (the poisoning defence). When the same clause
key has been corrected the same way at least twice, the next similar tender
pre-fills that value with a visible provenance note. Learned behaviour is
never silent: the pre-fill is a surfaced suggestion, never an auto-applied fact.
"""

from __future__ import annotations

import uuid
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import Role, is_label_role
from app.models import Correction, Tender

# "Correcting the same clause type twice → the third similar tender is
# pre-filled" (US-20). Two agreeing labels is the threshold.
MIN_LABELS = 2


@dataclass
class LearnedPrefill:
    key: str
    suggested_value: str
    note: str
    based_on_count: int
    source_tender_id: uuid.UUID | None


async def record_correction(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    tender_id: uuid.UUID,
    key: str,
    family: str,
    corrected_value: str,
    role: Role,
    name: str,
    rule_id: uuid.UUID | None = None,
) -> Correction:
    """Record one human correction. It becomes a training label only if the
    acting role is reviewer or above (SPEC §11.3)."""
    correction = Correction(
        org_id=org_id,
        tender_id=tender_id,
        rule_id=rule_id,
        family=family,
        key=key,
        corrected_value=corrected_value.strip(),
        corrected_by_role=role.value,
        corrected_by_name=(name or "").strip() or role.value,
        is_label=is_label_role(role),
    )
    session.add(correction)
    await session.flush()
    return correction


def _tender_ref(tender: Tender | None, tender_id: uuid.UUID) -> str:
    """Human-facing reference for the provenance note — the portal id when we
    have one ('Tender #GEM-1042'), else a short uuid prefix."""
    if tender is not None and tender.external_id:
        return tender.external_id
    return str(tender_id)[:8]


async def learned_prefill(
    session: AsyncSession,
    org_id: uuid.UUID,
    key: str,
    *,
    exclude_tender_id: uuid.UUID | None = None,
) -> LearnedPrefill | None:
    """The learned suggestion for a clause key, or None. Requires at least
    MIN_LABELS reviewer+ corrections that agree on the same value. Corrections
    made on `exclude_tender_id` are ignored so a tender never cites itself."""
    stmt = select(Correction).where(
        Correction.org_id == org_id,
        Correction.key == key,
        Correction.is_label.is_(True),
    )
    if exclude_tender_id is not None:
        stmt = stmt.where(Correction.tender_id != exclude_tender_id)
    labels = (
        (await session.execute(stmt.order_by(Correction.created_at))).scalars().all()
    )
    if not labels:
        return None

    # The agreed interpretation is the value corrected most often; it only
    # counts once it has been chosen the same way at least twice.
    counts = Counter(c.corrected_value for c in labels)
    value, n = counts.most_common(1)[0]
    if n < MIN_LABELS:
        return None

    # Cite the most recent correction that agrees on that value.
    source = next(c for c in reversed(labels) if c.corrected_value == value)
    tender = await session.get(Tender, source.tender_id)
    note = f"Based on your correction on Tender #{_tender_ref(tender, source.tender_id)}"
    return LearnedPrefill(
        key=key,
        suggested_value=value,
        note=note,
        based_on_count=n,
        source_tender_id=source.tender_id,
    )


async def prefills_for_keys(
    session: AsyncSession,
    org_id: uuid.UUID,
    keys,
    *,
    exclude_tender_id: uuid.UUID | None = None,
) -> dict[str, LearnedPrefill]:
    """Learned pre-fills for a set of clause keys, keyed by clause key. Used to
    enrich a tender's rule feed with any memory that applies."""
    out: dict[str, LearnedPrefill] = {}
    for key in set(keys):
        pf = await learned_prefill(
            session, org_id, key, exclude_tender_id=exclude_tender_id
        )
        if pf is not None:
            out[key] = pf
    return out
