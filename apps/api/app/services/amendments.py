"""The Amendment Watcher (US-07, SPEC §5.1).

A corrigendum is a new document version on an existing tender. We parse it,
extract its grounded rules, diff them against the tender's current rules,
surgically replace only the changed/added rules (re-grounded to the
corrigendum's page + box), re-check ONLY those affected rules, recompute the
decision, and emit a precise, cited alert with the EV before and after.

The whole tender is never reprocessed — the diff drives exactly what changes.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from bidproof_extractor import ElementRef

from app.confidence import band_for
from app.core.db import org_scoped_session
from app.models import Amendment, Decision, Document, Element, Rule, Tender
from app.observability import get_parse_logger, record_agent_run
from app.parsing import get_ladder
from app.services import checking, deciding, extraction, ingest
from app.storage import ObjectStorage

logger = logging.getLogger(__name__)


def _short(value: str | None) -> str:
    return (value or "—").strip()


async def apply_amendment(
    org_id: uuid.UUID,
    tender_id: uuid.UUID,
    corrigendum_bytes: bytes,
    storage: ObjectStorage,
    filename: str = "corrigendum.pdf",
    gateway=None,
) -> dict | None:
    started = datetime.now(timezone.utc)

    async with org_scoped_session(org_id) as session:
        tender = await session.get(Tender, tender_id)
        if tender is None:
            return None

    # 1. Ingest + parse the corrigendum as a new document version.
    document_id, parse_run_id = await ingest.add_document_to_tender(
        org_id, tender_id, filename=filename, data=corrigendum_bytes,
        storage=storage, kind="corrigendum",
    )
    await ingest.execute_parse_run(
        org_id=org_id, tender_id=tender_id, document_id=document_id,
        parse_run_id=parse_run_id, pdf_bytes=corrigendum_bytes,
        ladder=get_ladder(), parse_logger=get_parse_logger(),
    )

    # 2. Extract the corrigendum's grounded rules (in memory — not persisted
    #    as tender rules yet; the diff decides what to keep).
    async with org_scoped_session(org_id) as session:
        refs = [
            ElementRef(el_id=str(e.el_id), page_no=e.page_no, text=e.text)
            for e in (
                await session.execute(
                    select(Element)
                    .where(Element.document_id == document_id)
                    .order_by(Element.page_no, Element.seq)
                )
            ).scalars()
        ]
    corr_rules, _discarded, _note = await extraction.build_candidate_rules(refs, gateway)
    corr_by_key = {(r.family, r.key): r for r in corr_rules}

    # 3. Diff against the tender's current rules. A key may appear on several
    #    pages of the original, so group by (family, key) into occurrences.
    async with org_scoped_session(org_id) as session:
        current = (
            await session.execute(select(Rule).where(Rule.tender_id == tender_id))
        ).scalars().all()
        current_by_key: dict[tuple[str, str], list] = {}
        for r in current:
            current_by_key.setdefault((r.family, r.key), []).append(r)

        decision_before = (
            await session.execute(
                select(Decision).where(Decision.tender_id == tender_id)
            )
        ).scalar_one_or_none()
        ev_before = (
            float(decision_before.ev_inr)
            if decision_before and decision_before.ev_inr is not None
            else None
        )

    changes: list[dict] = []
    affected_rule_ids: list[uuid.UUID] = []

    async with org_scoped_session(org_id) as session:
        for (family, key), corr in corr_by_key.items():
            page_no = next((r.page_no for r in refs if r.el_id == corr.el_id), None)
            existing = current_by_key.get((family, key), [])
            old_value = existing[0].value_text if existing else None
            if existing and (old_value or "") == (corr.value or ""):
                continue  # restated unchanged — nothing to do

            # A corrigendum supersedes every prior occurrence of the key, so
            # the tender never holds two contradictory values. Deleting the
            # old rules cascades their verdicts.
            for stale in existing:
                await session.delete(await session.get(Rule, stale.rule_id))

            new_rule = Rule(
                org_id=org_id, tender_id=tender_id, document_id=document_id,
                family=family, key=key,
                requirement_text=corr.requirement_text, value_text=corr.value,
                el_id=uuid.UUID(corr.el_id), source=corr.source,
                status=corr.status, confidence=corr.confidence,
                band=band_for(corr.confidence),
                reason=f"{'revised' if existing else 'added'} by corrigendum: "
                       f"{corr.reason}",
            )
            session.add(new_rule)
            await session.flush()
            changes.append({
                "key": key, "family": family,
                "change": "revised" if existing else "added",
                "old_value": _short(old_value) if existing else None,
                "new_value": _short(corr.value), "page": page_no,
            })
            affected_rule_ids.append(new_rule.rule_id)

    # 4. Re-check ONLY the affected rules, then recompute the decision.
    recheck = await checking.recheck_rules(org_id, tender_id, affected_rule_ids, gateway)
    rules_broken = [
        c for c in recheck["changed"]
        if c["to"] in ("gap", "needs_human", "partial")
    ]

    # compute_decision reuses the value the tender was already valued at, so
    # the EV moves only because the corrigendum changed EMD/PBG/delivery.
    after = await deciding.compute_decision(org_id, tender_id, None)
    ev_after = after["ev_inr"] if after else None

    message = _build_message(tender.title, changes, rules_broken, ev_before, ev_after)

    async with org_scoped_session(org_id) as session:
        amendment = Amendment(
            org_id=org_id, tender_id=tender_id, document_id=document_id,
            message=message, changes=changes,
            rules_affected=[c["key"] for c in changes],
            rules_broken=[c["key"] for c in rules_broken],
            ev_before_inr=ev_before, ev_after_inr=ev_after,
        )
        session.add(amendment)
        await session.flush()
        amendment_id = str(amendment.id)

    await record_agent_run(
        org_id, tender_id, "amendment_watcher",
        duration_ms=int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
        meta={"changes": len(changes), "affected": [c["key"] for c in changes],
              "ev_before": ev_before, "ev_after": ev_after},
    )

    return {
        "amendment_id": amendment_id,
        "message": message,
        "changes": changes,
        "rules_affected": [c["key"] for c in changes],
        "rules_broken": [c["key"] for c in rules_broken],
        "rules_rechecked": recheck["rechecked"],
        "ev_before_inr": ev_before,
        "ev_after_inr": ev_after,
    }


def _lakh(value: float | None) -> str:
    return "unknown" if value is None else f"₹{value / 1e5:.2f}L"


def _build_message(title, changes, rules_broken, ev_before, ev_after) -> str:
    parts = []
    for c in changes:
        page = f", p.{c['page']}" if c.get("page") else ""
        if c["change"] == "revised":
            parts.append(f"{c['key']} {c['old_value']}→{c['new_value']} (corrigendum{page})")
        else:
            parts.append(f"{c['key']} added: {c['new_value']} (corrigendum{page})")
    change_text = "; ".join(parts) or "no extractable changes"
    broke = ", ".join(c["key"] for c in rules_broken)
    broke_text = f" Breaks {broke}." if broke else ""
    ev_text = f" EV {_lakh(ev_before)} → {_lakh(ev_after)}."
    return f"{change_text}.{broke_text}{ev_text}"
