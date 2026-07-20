"""Checking service (SPEC §5.5): runs the Matcher over every extracted rule
and the RiskScorer over the tender, persisting verdicts + risks.

Arithmetic rules never see the gateway — the code path hands them to pure
functions that cannot make a call. Only unresolved prose rules reach the
retriever + cited judge, and a judge without both citations is voided to
NEEDS_HUMAN."""

import logging
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import delete, select

from bidproof_matcher import (
    CheckRule,
    FactRef,
    KeywordRetriever,
    ProductRef,
    Verdict,
    VerdictResult,
    check_rule,
    parse_inr,
)
from bidproof_matcher.judge import (
    JUDGE_PROMPT_V1,
    build_judge_input,
    parse_judge_response,
    validate_judge_citations,
)
from bidproof_riskscorer import RiskInputs, RiskThresholds, score_risks

from app.confidence import band_for
from app.core.config import get_settings
from app.core.db import org_scoped_session
from app.llm.gateway import LLMGateway
from app.models import (
    CatalogueProduct,
    CompanyFact,
    RiskRow,
    Rule,
    Tender,
    VerdictRow,
)

logger = logging.getLogger(__name__)

CONF_JUDGE = 0.7
CONF_NEEDS_HUMAN = 0.4


def get_checking_gateway() -> LLMGateway:
    return LLMGateway()


async def _judge(gateway: LLMGateway | None, rule: CheckRule,
                 candidates: list[ProductRef]) -> VerdictResult:
    if gateway is None or not candidates:
        return VerdictResult(
            Verdict.NEEDS_HUMAN,
            "no judge available or no candidate products — a human decides",
            CONF_NEEDS_HUMAN, arithmetic=False)
    try:
        response = await gateway.complete(
            "mid",
            messages=[
                {"role": "system", "content": JUDGE_PROMPT_V1},
                {"role": "user", "content": build_judge_input(rule, candidates)},
            ],
            temperature=0,
        )
        raw = response["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.warning("judge call failed: %s", exc)
        return VerdictResult(Verdict.NEEDS_HUMAN,
                             "judge unavailable — a human decides",
                             CONF_NEEDS_HUMAN, arithmetic=False)

    call = parse_judge_response(raw)
    if call is None:
        return VerdictResult(Verdict.NEEDS_HUMAN,
                             "judge output rejected by schema — a human decides",
                             CONF_NEEDS_HUMAN, arithmetic=False)
    if not validate_judge_citations(call, rule, candidates):
        # The §5.5 rule: a judgement without BOTH citations is VOID.
        return VerdictResult(Verdict.NEEDS_HUMAN,
                             "judge voided: it did not cite both the tender "
                             "element and a retrieved product record",
                             CONF_NEEDS_HUMAN, arithmetic=False)
    return VerdictResult(
        Verdict(call.verdict),
        f"judge: {call.reason[:300]}",
        CONF_JUDGE, arithmetic=False,
        cited_product_id=call.product_id)


async def run_checks(org_id: uuid.UUID, tender_id: uuid.UUID,
                     gateway: LLMGateway | None = None) -> dict | None:
    import time

    checks_started = time.monotonic()
    async with org_scoped_session(org_id) as session:
        tender = await session.get(Tender, tender_id)
        if tender is None:
            return None
        rules = [
            CheckRule(
                rule_id=str(r.rule_id), family=r.family, key=r.key,
                requirement_text=r.requirement_text, value_text=r.value_text,
                el_id=str(r.el_id),
            )
            for r in (
                await session.execute(select(Rule).where(Rule.tender_id == tender_id))
            ).scalars()
        ]
        facts = [
            FactRef(id=str(f.id), fact_type=f.fact_type, value_text=f.value_text,
                    value_number=float(f.value_number) if f.value_number is not None else None,
                    fiscal_year=f.fiscal_year, valid_until=f.valid_until)
            for f in (await session.execute(select(CompanyFact))).scalars()
        ]
        products = [
            ProductRef(id=str(p.id), product_code=p.product_code,
                       product_name=p.product_name,
                       standards=tuple(p.standards or []),
                       lead_time_days=p.lead_time_days, specs=p.specs or {})
            for p in (await session.execute(select(CatalogueProduct))).scalars()
        ]
        closing_at = tender.closing_at

    today = date.today()
    retriever = KeywordRetriever()
    results: list[tuple[CheckRule, VerdictResult]] = []
    model_calls = 0
    for rule in rules:
        arithmetic_result = check_rule(rule, facts, products, today)
        if arithmetic_result is not None:
            results.append((rule, arithmetic_result))
            continue
        candidates = retriever.retrieve(rule.requirement_text, products)
        judged = await _judge(gateway, rule, candidates)
        model_calls += 1 if gateway is not None and candidates else 0
        results.append((rule, judged))

    by_key = {r.key: (r, v) for r, v in results}
    risk_inputs = _build_risk_inputs(by_key, closing_at, products)
    settings = get_settings()
    risk_flags = score_risks(
        risk_inputs,
        RiskThresholds(
            pbg_max_percent=settings.risk_pbg_max_percent,
            emd_max_percent_of_value=settings.risk_emd_max_percent_of_value,
        ),
    )

    async with org_scoped_session(org_id) as session:
        rule_ids = [uuid.UUID(r.rule_id) for r, _ in results]
        await session.execute(delete(VerdictRow).where(VerdictRow.tender_id == tender_id))
        await session.execute(delete(RiskRow).where(RiskRow.tender_id == tender_id))
        for rule, result in results:
            session.add(VerdictRow(
                org_id=org_id, tender_id=tender_id,
                rule_id=uuid.UUID(rule.rule_id),
                verdict=result.verdict.value, reason=result.reason,
                confidence=result.confidence, band=band_for(result.confidence),
                arithmetic=result.arithmetic,
                cited_fact_id=uuid.UUID(result.cited_fact_id) if result.cited_fact_id else None,
                cited_product_id=uuid.UUID(result.cited_product_id) if result.cited_product_id else None,
            ))
        for flag in risk_flags:
            session.add(RiskRow(
                org_id=org_id, tender_id=tender_id, code=flag.code,
                severity=flag.severity, message=flag.message,
                rupee_impact=flag.rupee_impact,
                el_id=uuid.UUID(flag.el_id) if flag.el_id else None,
            ))

    counts: dict[str, int] = {}
    for _, result in results:
        counts[result.verdict.value] = counts.get(result.verdict.value, 0) + 1

    import time

    from app.observability import record_agent_run

    duration_ms = int((time.monotonic() - checks_started) * 1000)
    await record_agent_run(
        org_id, tender_id, "matcher", duration_ms=duration_ms,
        model_role="mid" if model_calls else None,
        prompt_version="judge_v1" if model_calls else None,
        meta={"rules_checked": len(results), "verdicts": counts,
              "model_calls": model_calls},
    )
    await record_agent_run(
        org_id, tender_id, "riskscorer", duration_ms=0,
        meta={"flags": [f.code for f in risk_flags]},
    )
    return {
        "rules_checked": len(results),
        "verdicts": counts,
        "risks": len(risk_flags),
        "model_calls": model_calls,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def _build_risk_inputs(by_key: dict, closing_at, products: list[ProductRef]) -> RiskInputs:
    def value_of(key: str) -> tuple[str | None, str | None]:
        entry = by_key.get(key)
        return (entry[0].value_text, entry[0].el_id) if entry else (None, None)

    pbg_text, pbg_el = value_of("pbg_percent")
    emd_text, emd_el = value_of("emd_amount")
    delivery_text, delivery_el = value_of("delivery_days")
    query_text, query_el = value_of("prebid_query_window_days")
    turnover_entry = by_key.get("min_turnover")

    # Tender value proxy is unknown unless triage extracted one; the EV story
    # (US-06) formalises it. Use None rather than a guess.
    tender_value = None

    def to_float(text: str | None) -> float | None:
        try:
            return float(text) if text is not None else None
        except ValueError:
            return None

    lead_times = [p.lead_time_days for p in products if p.lead_time_days is not None]
    return RiskInputs(
        tender_value_inr=tender_value,
        closing_at=closing_at,
        now=datetime.now(timezone.utc),
        best_lead_time_days=min(lead_times) if lead_times else None,
        pbg_percent=to_float(pbg_text),
        pbg_el_id=pbg_el,
        emd_amount_inr=parse_inr(emd_text),
        emd_el_id=emd_el,
        delivery_days=int(delivery_text) if delivery_text and delivery_text.isdigit() else None,
        delivery_el_id=delivery_el,
        query_window_days=int(query_text) if query_text and query_text.isdigit() else None,
        query_el_id=query_el,
    )


async def check_after_extract(org_id: uuid.UUID, tender_id: uuid.UUID) -> None:
    """Post-extraction hook: checking must never take ingestion down."""
    try:
        await run_checks(org_id, tender_id, gateway=get_checking_gateway())
    except Exception:
        logger.exception("checking failed for tender %s", tender_id)
