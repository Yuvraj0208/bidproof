"""QuestionWriter service (US-08, SPEC §5.8): for every rule we FAIL (verdict
GAP), draft a grounded, cited pre-bid query letter — batched with the query
deadline. Drafts only; the system never sends (SPEC §10)."""

import logging
import uuid
from datetime import timedelta

from sqlalchemy import delete, select

from bidproof_questionwriter import (
    FailedRule,
    QUESTION_PROMPT_V1,
    draft_letter,
    keep_polished_body,
)

from app.core.db import org_scoped_session
from app.llm.gateway import LLMGateway
from app.models import (
    CompanyFact,
    Element,
    Organization,
    QueryLetter,
    Rule,
    Tender,
    VerdictRow,
)
from app.observability import record_agent_run

logger = logging.getLogger(__name__)

# We draft letters for the requirements we fail — the ones a buyer could
# relax. GAP = we do not meet it.
QUERYABLE_VERDICTS = {"gap"}


def get_question_gateway() -> LLMGateway:
    return LLMGateway()


async def _polish(gateway: LLMGateway | None, draft) -> str:
    if gateway is None:
        return draft.body
    try:
        response = await gateway.complete(
            "strong",
            messages=[
                {"role": "system", "content": QUESTION_PROMPT_V1},
                {"role": "user", "content": f"<letter_draft>\n{draft.body}\n</letter_draft>"},
            ],
            temperature=0.3,
        )
        polished = response["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.warning("question polish failed: %s", exc)
        polished = None
    return keep_polished_body(draft, polished)


async def generate_questions(
    org_id: uuid.UUID, tender_id: uuid.UUID, gateway: LLMGateway | None = None
) -> dict | None:
    async with org_scoped_session(org_id) as session:
        tender = await session.get(Tender, tender_id)
        if tender is None:
            return None
        org = await session.get(Organization, org_id)
        company_name = org.name if org else "the Bidder"

        legal = (
            await session.execute(
                select(CompanyFact.legal_entity)
                .where(CompanyFact.fact_type == "turnover")
                .where(CompanyFact.legal_entity.is_not(None))
                .limit(1)
            )
        ).scalar_one_or_none()
        if legal:
            company_name = legal

        rows = (
            await session.execute(
                select(VerdictRow, Rule, Element)
                .join(Rule, VerdictRow.rule_id == Rule.rule_id)
                .join(Element, Rule.el_id == Element.el_id)
                .where(VerdictRow.tender_id == tender_id)
                .where(VerdictRow.verdict.in_(QUERYABLE_VERDICTS))
                .order_by(Rule.family, Rule.key)
            )
        ).all()

        window_row = (
            await session.execute(
                select(Rule.value_text)
                .where(Rule.tender_id == tender_id)
                .where(Rule.key == "prebid_query_window_days")
                .limit(1)
            )
        ).scalar_one_or_none()
        closing_at = tender.closing_at

    query_deadline = None
    if closing_at is not None and window_row and window_row.isdigit():
        query_deadline = (closing_at - timedelta(days=int(window_row))).date()

    failed = [
        FailedRule(
            rule_id=str(r.rule_id), family=r.family, key=r.key,
            requirement_text=r.requirement_text, el_id=str(e.el_id),
            page_no=e.page_no, verdict_reason=v.reason,
        )
        for v, r, e in rows
    ]

    letters = []
    for rule in failed:
        draft = draft_letter(rule, company_name, query_deadline)
        body = await _polish(gateway, draft)
        letters.append((rule, draft, body))

    async with org_scoped_session(org_id) as session:
        await session.execute(
            delete(QueryLetter).where(QueryLetter.tender_id == tender_id)
        )
        for rule, draft, body in letters:
            session.add(QueryLetter(
                org_id=org_id, tender_id=tender_id,
                rule_id=uuid.UUID(rule.rule_id), el_id=uuid.UUID(rule.el_id),
                rule_key=rule.key, page_no=rule.page_no,
                subject=draft.subject, body=body, query_deadline=query_deadline,
                status="draft",
            ))

    await record_agent_run(
        org_id, tender_id, "questionwriter", duration_ms=0,
        model_role="strong" if gateway is not None else None,
        prompt_version="question_v1" if gateway is not None else None,
        meta={"letters": len(letters), "query_deadline": str(query_deadline)},
    )
    return {
        "letters": len(letters),
        "query_deadline": str(query_deadline) if query_deadline else None,
        "for_rules": [rule.key for rule, _, _ in letters],
    }


async def generate_after_check(org_id: uuid.UUID, tender_id: uuid.UUID) -> None:
    """Post-check hook: drafting must never take the pipeline down."""
    try:
        await generate_questions(org_id, tender_id, gateway=get_question_gateway())
    except Exception:
        logger.exception("question generation failed for tender %s", tender_id)
