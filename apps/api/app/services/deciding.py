"""Deciding service (US-06): gather verdicts + rule values, run the
deterministic Decider, persist the decision as pending_signoff, and write
every human action to the append-only audit log."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from bidproof_decider import DecisionOutcome, EvConfig, decide
from bidproof_matcher import parse_inr
from bidproof_triage import extract_value_inr

from app.confidence import band_for
from app.core.config import get_settings
from app.core.db import org_scoped_session
from app.models import AuditLog, Decision, Element, Document, Rule, Tender, VerdictRow

logger = logging.getLogger(__name__)


def _config() -> EvConfig:
    settings = get_settings()
    return EvConfig(
        p_win=settings.ev_p_win,
        profit_margin_percent=settings.ev_profit_margin_percent,
        man_days=settings.ev_man_days,
        loaded_day_rate_inr=settings.ev_loaded_day_rate_inr,
        capital_rate_annual=settings.ev_capital_rate_annual,
        lock_months=settings.ev_lock_months,
    )


async def compute_decision(
    org_id: uuid.UUID,
    tender_id: uuid.UUID,
    tender_value_inr: float | None = None,
    actor: str = "system",
) -> dict | None:
    async with org_scoped_session(org_id) as session:
        tender = await session.get(Tender, tender_id)
        if tender is None:
            return None

        verdict_rows = (
            await session.execute(
                select(VerdictRow, Rule)
                .join(Rule, VerdictRow.rule_id == Rule.rule_id)
                .where(VerdictRow.tender_id == tender_id)
            )
        ).all()
        verdicts = [
            {"family": r.family, "key": r.key, "verdict": v.verdict,
             "rule_id": str(r.rule_id)}
            for v, r in verdict_rows
        ]
        values = {r.key: r.value_text for _, r in verdict_rows}

        if tender_value_inr is None:
            # Fall back to the largest amount in the document — regex only,
            # surfaced as such; the human corrects it in the Decision Room.
            document = (
                await session.execute(
                    select(Document.id).where(Document.tender_id == tender_id)
                )
            ).scalar_one_or_none()
            if document:
                texts = (
                    await session.execute(
                        select(Element.text).where(Element.document_id == document)
                    )
                ).scalars()
                tender_value_inr = extract_value_inr(" ".join(texts))

    emd = parse_inr(values.get("emd_amount"))
    try:
        pbg = float(values["pbg_percent"]) if values.get("pbg_percent") else None
    except ValueError:
        pbg = None

    outcome: DecisionOutcome = decide(
        verdicts, tender_value_inr, emd, pbg, _config()
    )

    async with org_scoped_session(org_id) as session:
        existing = (
            await session.execute(
                select(Decision).where(Decision.tender_id == tender_id)
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = Decision(org_id=org_id, tender_id=tender_id,
                                recommendation="needs_human", confidence=0,
                                band="red", reason="")
            session.add(existing)
        existing.recommendation = outcome.recommendation
        existing.ev_inr = outcome.ev_inr
        existing.terms = outcome.terms
        existing.gate_failed = outcome.gate_failed
        existing.confidence = outcome.confidence
        existing.band = band_for(outcome.confidence)
        existing.reason = outcome.reason
        existing.status = "pending_signoff"   # Checkpoint 4 NEVER auto-passes
        existing.signed_off_by = None
        existing.signed_off_at = None
        session.add(AuditLog(
            org_id=org_id, actor=actor, action="decision_computed",
            tender_id=tender_id,
            details={"recommendation": outcome.recommendation,
                     "ev_inr": outcome.ev_inr,
                     "tender_value_inr": tender_value_inr},
        ))
        await session.flush()
        return _decision_dict(existing)


async def sign_off(org_id: uuid.UUID, tender_id: uuid.UUID, name: str) -> dict | None:
    async with org_scoped_session(org_id) as session:
        decision = (
            await session.execute(
                select(Decision).where(Decision.tender_id == tender_id)
            )
        ).scalar_one_or_none()
        if decision is None:
            return None
        decision.status = "signed_off"
        decision.signed_off_by = name
        decision.signed_off_at = datetime.now(timezone.utc)
        session.add(AuditLog(
            org_id=org_id, actor=name, action="decision_signed_off",
            tender_id=tender_id,
            details={"recommendation": decision.recommendation,
                     "ev_inr": float(decision.ev_inr) if decision.ev_inr is not None else None},
        ))
        await session.flush()
        return _decision_dict(decision)


async def override(
    org_id: uuid.UUID, tender_id: uuid.UUID, name: str,
    recommendation: str, reason: str,
) -> dict | None:
    async with org_scoped_session(org_id) as session:
        decision = (
            await session.execute(
                select(Decision).where(Decision.tender_id == tender_id)
            )
        ).scalar_one_or_none()
        if decision is None:
            return None
        previous = decision.recommendation
        decision.recommendation = recommendation
        decision.status = "overridden"
        decision.signed_off_by = name
        decision.signed_off_at = datetime.now(timezone.utc)
        decision.reason = f"OVERRIDDEN by {name}: {reason}"
        session.add(AuditLog(
            org_id=org_id, actor=name, action="decision_overridden",
            tender_id=tender_id,
            details={"from": previous, "to": recommendation, "reason": reason},
        ))
        await session.flush()
        return _decision_dict(decision)


def _decision_dict(decision: Decision) -> dict:
    return {
        "tender_id": str(decision.tender_id),
        "recommendation": decision.recommendation,
        "ev_inr": float(decision.ev_inr) if decision.ev_inr is not None else None,
        "terms": decision.terms,
        "gate_failed": decision.gate_failed,
        "confidence": decision.confidence,
        "band": decision.band,
        "reason": decision.reason,
        "status": decision.status,
        "signed_off_by": decision.signed_off_by,
    }
