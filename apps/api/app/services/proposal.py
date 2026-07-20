"""Proposal generation (US-09, SPEC §5.7): Librarian retrieves winning
blocks, the ProposalWriter drafts section by section with enforced source
tags, and the FactChecker marks every claim. Runs only after a GO decision.
"""

import logging
import time
import uuid
from dataclasses import asdict

from sqlalchemy import delete, select

from bidproof_factchecker import check_text, verified_percentage
from bidproof_librarian import LibraryBlock, rank_blocks
from bidproof_proposalwriter import (
    DEFAULT_SECTIONS,
    WRITER_PROMPT_V1,
    build_fact_context,
    deterministic_section,
    enforce_source_tags,
)

from app.core.db import org_scoped_session
from app.llm.gateway import LLMGateway
from app.models import (
    CatalogueProduct,
    CompanyFact,
    Decision,
    LibraryBlockRow,
    Organization,
    Proposal,
    ProposalSection,
    Rule,
    Tender,
)
from app.observability import record_agent_run

logger = logging.getLogger(__name__)


class NoGoDecisionError(Exception):
    """A proposal is drafted only after a signed-off direction of GO."""


def get_writer_gateway() -> LLMGateway:
    return LLMGateway()


async def _polish_section(
    gateway: LLMGateway | None,
    section_tag: str,
    draft: str,
    fact_lines: str,
    style_blocks: list[LibraryBlock],
) -> str:
    if gateway is None:
        return draft
    style = "\n---\n".join(b.text for b in style_blocks) or "none available"
    user = (
        f"<facts>\n{fact_lines}\n</facts>\n"
        f"<style_reference>\n{style}\n</style_reference>\n"
        f"<draft section=\"{section_tag}\">\n{draft}\n</draft>"
    )
    try:
        response = await gateway.complete(
            "strong",
            messages=[
                {"role": "system", "content": WRITER_PROMPT_V1},
                {"role": "user", "content": user},
            ],
            temperature=0.4,
        )
        polished = response["choices"][0]["message"]["content"]
        return polished if polished and polished.strip() else draft
    except Exception as exc:
        logger.warning("writer polish failed for %s: %s", section_tag, exc)
        return draft


async def generate_proposal(
    org_id: uuid.UUID,
    tender_id: uuid.UUID,
    gateway: LLMGateway | None = None,
    sections: list[str] | None = None,
) -> dict | None:
    started = time.monotonic()

    async with org_scoped_session(org_id) as session:
        tender = await session.get(Tender, tender_id)
        if tender is None:
            return None
        decision = (
            await session.execute(
                select(Decision).where(Decision.tender_id == tender_id)
            )
        ).scalar_one_or_none()
        if decision is None or decision.recommendation != "go":
            raise NoGoDecisionError(
                "a proposal is drafted only after a GO decision (US-09)"
            )

        org = await session.get(Organization, org_id)
        company_name = org.name if org else "the Bidder"

        facts = [
            {
                "id": f.id, "fact_type": f.fact_type, "value_text": f.value_text,
                "value_number": float(f.value_number) if f.value_number is not None else None,
                "fiscal_year": f.fiscal_year, "legal_entity": f.legal_entity,
                "valid_until": str(f.valid_until) if f.valid_until else None,
            }
            for f in (await session.execute(select(CompanyFact))).scalars()
        ]
        products = [
            {
                "id": p.id, "product_code": p.product_code,
                "product_name": p.product_name,
                "standards": list(p.standards or []),
                "lead_time_days": p.lead_time_days,
                "capacity_per_month": p.capacity_per_month,
            }
            for p in (await session.execute(select(CatalogueProduct))).scalars()
        ]
        requirements = [
            r.requirement_text
            for r in (
                await session.execute(select(Rule).where(Rule.tender_id == tender_id))
            ).scalars()
        ]
        approved_blocks = [
            LibraryBlock(section_tag=b.section_tag, text=b.text,
                         outcome=b.outcome, source_name=b.source_name)
            for b in (
                await session.execute(
                    select(LibraryBlockRow)
                    .where(LibraryBlockRow.quarantined.is_(False))
                )
            ).scalars()
        ]
        tender_title = tender.title

    tagged = build_fact_context(facts, products)
    valid_tags = {t.tag for t in tagged}
    facts_by_tag = {t.tag: t.text for t in tagged}
    fact_lines = "\n".join(f"{t.tag} {t.text}" for t in tagged)
    context_text = f"{tender_title} " + " ".join(requirements)

    section_list = sections or DEFAULT_SECTIONS
    format_source = "tender_dictated" if sections else "default_template"

    built: list[dict] = []
    totals = {"claims": 0, "verified": 0, "contradicted": 0,
              "cannot_verify": 0, "dropped_untagged": 0}
    blocks_used = 0

    for position, section_tag in enumerate(section_list):
        style_blocks = rank_blocks(section_tag, context_text, approved_blocks)
        blocks_used += len(style_blocks)
        draft = deterministic_section(
            section_tag, tender_title, company_name, tagged, requirements
        )
        candidate = await _polish_section(
            gateway, section_tag, draft, fact_lines, style_blocks
        )
        kept, dropped = enforce_source_tags(
            candidate, valid_tags, allowed_context=(tender_title,)
        )
        if not kept.strip():
            # The polished text lost all grounding — the grounded draft stands.
            kept, dropped = enforce_source_tags(
                draft, valid_tags, allowed_context=(tender_title,)
            )
        claims = check_text(kept, facts_by_tag, ignore_context=(tender_title,))
        totals["claims"] += len(claims)
        for claim in claims:
            totals[claim.status] = totals.get(claim.status, 0) + 1
        totals["dropped_untagged"] += dropped
        built.append({
            "section_tag": section_tag, "position": position, "content": kept,
            "claims": [asdict(c) for c in claims],
            "verified_pct": verified_percentage(claims),
            "dropped_untagged": dropped,
        })

    duration_ms = int((time.monotonic() - started) * 1000)

    async with org_scoped_session(org_id) as session:
        existing = (
            await session.execute(
                select(Proposal).where(Proposal.tender_id == tender_id)
            )
        ).scalar_one_or_none()
        if existing is not None:
            await session.execute(
                delete(Proposal).where(Proposal.id == existing.id)
            )
        proposal = Proposal(
            org_id=org_id, tender_id=tender_id, status="draft",
            format_source=format_source, duration_ms=duration_ms,
        )
        session.add(proposal)
        await session.flush()
        for section in built:
            session.add(ProposalSection(org_id=org_id, proposal_id=proposal.id,
                                        **section))

    await record_agent_run(
        org_id, tender_id, "librarian", duration_ms=0,
        meta={"blocks_retrieved": blocks_used},
    )
    await record_agent_run(
        org_id, tender_id, "proposal_writer", duration_ms=duration_ms,
        model_role="strong" if gateway is not None else None,
        prompt_version="writer_v1" if gateway is not None else None,
        meta={"sections": len(built), "format_source": format_source,
              "dropped_untagged": totals["dropped_untagged"]},
    )
    await record_agent_run(
        org_id, tender_id, "factchecker", duration_ms=0,
        meta={k: totals[k] for k in
              ("claims", "verified", "contradicted", "cannot_verify")},
    )

    return {
        "sections": len(built),
        "duration_ms": duration_ms,
        "format_source": format_source,
        **totals,
    }
