"""Proposal generation (US-09, SPEC §5.7): Librarian retrieves winning
blocks, the ProposalWriter drafts section by section with enforced source
tags, and the FactChecker marks every claim. Runs only after a GO decision.
"""

import logging
import re
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy import delete, select

from bidproof_factchecker import check_text, verified_percentage
from bidproof_librarian import LibraryBlock, rank_blocks
from bidproof_proposalwriter import (
    DEFAULT_SECTIONS,
    WRITER_PROMPT_V1,
    build_fact_context,
    deterministic_section,
    enforce_source_tags,
    requirements_covered_pct,
    style_match_pct,
)

from app.core.db import org_scoped_session
from app.llm.gateway import LLMGateway, extract_text
from app.models import (
    AuditLog,
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


# A model sometimes echoes the prompt's own fences ("<draft section=...>") into
# its answer. That scaffolding reached an exported customer document once
# (docs/FINISH_STATUS.md D1) — strip it defensively, never ship it.
_SCAFFOLD_RE = re.compile(
    r"</?(?:draft|facts|requirements|style_reference|section)\b[^>]*>",
    re.IGNORECASE,
)


# Source tags — [F:xxxxxxxx] for a company fact, [P:xxxxxxxx] for a product —
# are the proof chain for prose. The FactChecker parses them and every claim's
# `source_tag` comes from them, so they MUST stay in the stored content.
#
# They must equally never reach a reader. A tender proposal handed to a buyer
# with "[F:f86aed8e]" in the middle of a sentence looks broken, and a bid can be
# rejected on presentation alone. So they are stripped at the moment of
# rendering, not at the moment of writing.
_SOURCE_TAG_RE = re.compile(r"\s*\[(?:F|P):[0-9a-f]{6,12}\]", re.IGNORECASE)


def render_for_reader(text: str) -> str:
    """The section as a human should see it: same prose, no internal tags.

    Removing a tag leaves debris — " ," where a tag preceded a comma, a run of
    twelve product tags collapsing into a gap, a space before a full stop. Those
    are tidied here so the sentence reads as though it were written that way.
    """
    if not text:
        return ""
    cleaned = _SOURCE_TAG_RE.sub("", text)
    # The tag sat before the punctuation it belonged to:
    #   "certification , ISO" -> "certification, ISO"
    cleaned = re.sub(r"[ \t]+([,.;:!?])", r"\1", cleaned)
    # Collapse the horizontal gap a removed run of tags left behind, without
    # touching the newlines that separate paragraphs.
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    return cleaned.strip()


def strip_scaffolding(text: str) -> str:
    cleaned = _SCAFFOLD_RE.sub("", text)
    # Drop a leading echoed label like 'Company Profile:' or 'Section:'
    cleaned = re.sub(r"\A\s*(?:section\s*:|title\s*:)\s*", "", cleaned,
                     flags=re.IGNORECASE)
    return cleaned.strip()


# A model sometimes narrates its plan instead of writing the section
# ("Okay, let me start by...", "We are writing the X section", "Steps:").
# That is private thinking, not bid prose — it must never reach a document.
_REASONING_MARKERS = (
    "we are writing", "let me start", "let me begin", "okay, let",
    "first, i need", "my job is to", "the user is asking", "the user wants",
    "the user provided", "steps:", "approach:", "i need to parse",
    "we must avoid", "however, the requirement is", "never compute, convert",
    "the requirements are repeated",
)


def looks_like_reasoning(text: str) -> bool:
    """True when the text reads as the model's planning rather than the
    section itself. Checked on the opening, where narration always starts."""
    head = " ".join(text.lower().split())[:400]
    return any(marker in head for marker in _REASONING_MARKERS)


async def _polish_section(
    gateway: LLMGateway | None,
    section_tag: str,
    draft: str,
    fact_lines: str,
    style_blocks: list[LibraryBlock],
    requirements: list[str] | None = None,
) -> str:
    if gateway is None:
        return draft
    style = "\n---\n".join(b.text for b in style_blocks) or "none available"
    wanted = "\n".join(f"- {r}" for r in (requirements or [])[:12]) or "none stated"
    user = (
        f"<facts>\n{fact_lines}\n</facts>\n"
        f"<requirements>\n{wanted}\n</requirements>\n"
        f"<style_reference>\n{style}\n</style_reference>\n"
        f"<draft section=\"{section_tag}\">\n{draft}\n</draft>"
    )
    messages = [
        {"role": "system", "content": WRITER_PROMPT_V1},
        {"role": "user", "content": user},
    ]
    # One strict retry if the model narrates its plan instead of writing the
    # section; then the grounded draft stands. Never ship thinking as prose.
    for attempt in range(2):
        if attempt:
            messages = messages + [
                {"role": "user", "content": (
                    "That reply narrated your process instead of writing the "
                    "section. Reply again with ONLY the finished section prose, "
                    "beginning at its first sentence. No preamble, no planning, "
                    "no restating of the task."
                )},
            ]
        try:
            response = await gateway.complete(
                "strong", messages=messages, temperature=0.4, max_tokens=1600,
            )
            polished = strip_scaffolding(extract_text(response))
        except Exception as exc:
            logger.warning("writer polish failed for %s: %s", section_tag, exc)
            return draft
        if polished and not looks_like_reasoning(polished):
            return polished
        logger.warning(
            "writer returned narration for %s (attempt %d)", section_tag, attempt + 1
        )
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
            gateway, section_tag, draft, fact_lines, style_blocks, requirements
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
            "requirements_covered_pct": requirements_covered_pct(kept, requirements),
            "style_match_pct": style_match_pct(kept, [b.text for b in style_blocks]),
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


# --- Section-by-section approval (US-11) ------------------------------------

OPEN_FLAG_STATUSES = {"contradicted", "cannot_verify"}


def open_flags(claims: list[dict]) -> list[str]:
    """A section cannot be approved while any claim is contradicted or
    unverifiable — those are the flags a human must resolve first.

    A claim carrying a `resolution` has been dealt with by a named person and
    no longer blocks. Until `resolve_claim` existed this was a dead end: the
    approve button said "resolve open flags first" and nothing in the product
    could resolve one.
    """
    return [
        c["status"]
        for c in claims
        if c["status"] in OPEN_FLAG_STATUSES and not c.get("resolution")
    ]


# What a person may do with a flagged claim. Both are decisions, and both are
# recorded — the point of a checkpoint is that someone's name is against it.
RESOLUTIONS = {
    # The sentence goes. The writer claimed more than the company can show,
    # and the safest correction is for it not to be in the proposal.
    "drop",
    # The sentence stays, vouched for by a named person with a reason. Used
    # when the claim is true but the capability database cannot prove it —
    # a gap in our data, not a false statement.
    "accept",
}


def validate_resolution(action: str, by: str, reason: str) -> str | None:
    """Why a resolution would be refused, or None if it is well-formed.

    Separate from the database work so the rules can be read — and tested —
    without one. Dropping needs no justification because removing an unproven
    sentence is the safe direction; keeping one does.
    """
    if action not in RESOLUTIONS:
        return f"unknown action {action!r} — expected drop or accept"
    if len(by.strip()) < 2:
        return "a name is required — a resolution is attributable"
    if action == "accept" and len(reason.strip()) < 10:
        return (
            "accepting a flagged claim needs a written reason — it is on the "
            "record that a person vouched for it"
        )
    return None


async def resolve_claim(
    org_id: uuid.UUID,
    tender_id: uuid.UUID,
    section_id: uuid.UUID,
    claim_index: int,
    action: str,
    by: str,
    reason: str,
) -> tuple[dict | None, str | None]:
    """Resolve one flagged claim, so its section can be approved.

    This is the missing half of Checkpoint 5. SPEC §7 requires a human to
    "resolve every flag", and the export blocker refuses while a claim is
    contradicted — but there was no way to act on one, so a flagged section
    could never be approved or exported except by overriding the whole export.
    """
    refusal = validate_resolution(action, by, reason)
    if refusal is not None:
        return None, refusal

    async with org_scoped_session(org_id) as session:
        section = await session.get(ProposalSection, section_id)
        if section is None or section.org_id != org_id:
            return None, None
        claims = list(section.claims or [])
        if not 0 <= claim_index < len(claims):
            return None, f"no claim at index {claim_index}"

        claim = dict(claims[claim_index])
        if claim["status"] not in OPEN_FLAG_STATUSES:
            return None, "that claim is not flagged"

        claim["resolution"] = action
        claim["resolved_by"] = by.strip()
        claim["resolved_reason"] = reason.strip()
        claim["resolved_at"] = datetime.now(timezone.utc).isoformat()
        claims[claim_index] = claim

        if action == "drop":
            # Remove the sentence itself, not just the badge. Leaving the prose
            # in place while marking the claim resolved would export a sentence
            # the company cannot support.
            section.content = _remove_sentence(section.content, claim["text"])

        section.claims = claims
        # Approval is a separate, deliberate act: resolving the last flag
        # unblocks the button, it does not press it.
        session.add(AuditLog(
            org_id=org_id, tender_id=tender_id, actor=by.strip(),
            action=f"proposal_claim_{action}",
            details={
                "section": section.section_tag,
                "claim": claim["text"][:300],
                "status": claim["status"],
                "reason": reason.strip(),
            },
        ))
        await session.flush()
        return _section_dict(section), None


def _remove_sentence(content: str, sentence: str) -> str:
    """Take one sentence out of a section, leaving the rest readable."""
    if not content or not sentence:
        return content or ""
    out = content.replace(sentence.strip(), "")
    # Dropping a sentence mid-paragraph leaves a double space, and dropping the
    # only sentence of a paragraph leaves a blank line.
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


async def _load_writer_context(org_id: uuid.UUID, tender_id: uuid.UUID):
    async with org_scoped_session(org_id) as session:
        tender = await session.get(Tender, tender_id)
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
    tagged = build_fact_context(facts, products)
    facts_by_tag = {t.tag: t.text for t in tagged}
    valid_tags = {t.tag for t in tagged}
    return tender, tagged, facts_by_tag, valid_tags, requirements


async def edit_section(
    org_id: uuid.UUID, tender_id: uuid.UUID, section_id: uuid.UUID, content: str
) -> dict | None:
    """A human edits a section. The edit is re-grounded (untagged facts
    dropped) and re-fact-checked, so approving a section is only possible once
    it is genuinely clean — resolving a flag is real, not a checkbox."""
    tender, _tagged, facts_by_tag, valid_tags, _reqs = await _load_writer_context(
        org_id, tender_id
    )
    kept, dropped = enforce_source_tags(
        content, valid_tags, allowed_context=(tender.title,) if tender else ()
    )
    claims = check_text(kept, facts_by_tag,
                        ignore_context=(tender.title,) if tender else ())

    async with org_scoped_session(org_id) as session:
        section = await session.get(ProposalSection, section_id)
        if section is None or section.org_id != org_id:
            return None
        section.content = kept
        section.claims = [asdict(c) for c in claims]
        section.verified_pct = verified_percentage(claims)
        section.dropped_untagged = dropped
        # An edited section is no longer approved — it must be re-approved.
        section.approved = False
        section.approved_by = None
        section.approved_at = None
        await session.flush()
        return _section_dict(section)


async def approve_section(
    org_id: uuid.UUID, tender_id: uuid.UUID, section_id: uuid.UUID, name: str
) -> tuple[dict | None, str | None]:
    """Approve ONE section (Checkpoint 5 — never automatic, never bulk).
    Returns (section, error). Refuses while any flag is open."""
    async with org_scoped_session(org_id) as session:
        section = await session.get(ProposalSection, section_id)
        if section is None or section.org_id != org_id:
            return None, None
        flags = open_flags(section.claims or [])
        if flags:
            return None, (
                f"section has {len(flags)} unresolved flag(s) "
                f"({', '.join(sorted(set(flags)))}) — resolve them before approving"
            )
        section.approved = True
        section.approved_by = name
        section.approved_at = datetime.now(timezone.utc)
        await session.flush()
        return _section_dict(section), None


async def approve_sections(
    org_id: uuid.UUID, tender_id: uuid.UUID,
    section_ids: list[uuid.UUID], name: str,
) -> tuple[dict | None, str | None]:
    """Approve several sections at once, under one name (Checkpoint 5).

    Sections carrying an unresolved flag are skipped rather than approved, and
    reported back by name. That is not the old refusal in disguise: a flagged
    claim can now be dropped or accepted in the same screen, so this is a
    step the operator can clear, not a wall.
    """
    if len(name.strip()) < 2:
        return None, "a name is required — an approval is attributable"
    if not section_ids:
        return None, "no sections selected"

    approved: list[str] = []
    skipped: list[dict] = []
    async with org_scoped_session(org_id) as session:
        sections = (
            await session.execute(
                select(ProposalSection).where(
                    ProposalSection.id.in_(section_ids)
                )
            )
        ).scalars().all()

        for section in sections:
            if section.org_id != org_id:
                continue
            flags = open_flags(section.claims or [])
            if flags:
                skipped.append({
                    "section": section.section_tag,
                    "reason": f"{len(flags)} unresolved flag(s)",
                })
                continue
            if section.approved:
                continue
            section.approved = True
            section.approved_by = name.strip()
            section.approved_at = datetime.now(timezone.utc)
            approved.append(section.section_tag)

        session.add(AuditLog(
            org_id=org_id, tender_id=tender_id, actor=name.strip(),
            action="proposal_sections_approved",
            details={"approved": approved, "skipped": skipped},
        ))
        await session.flush()

    return {"approved": approved, "skipped": skipped}, None


async def readiness(org_id: uuid.UUID, tender_id: uuid.UUID) -> dict | None:
    async with org_scoped_session(org_id) as session:
        proposal = (
            await session.execute(
                select(Proposal).where(Proposal.tender_id == tender_id)
            )
        ).scalar_one_or_none()
        if proposal is None:
            return None
        sections = (
            await session.execute(
                select(ProposalSection).where(
                    ProposalSection.proposal_id == proposal.id
                )
            )
        ).scalars().all()
    approved = [s for s in sections if s.approved]
    open_flag_sections = [s for s in sections if open_flags(s.claims or [])]
    return {
        "total": len(sections),
        "approved": len(approved),
        "sections_with_open_flags": len(open_flag_sections),
        "ready": len(sections) > 0 and len(approved) == len(sections),
    }


def _section_dict(section: ProposalSection) -> dict:
    return {
        "id": str(section.id), "section_tag": section.section_tag,
        "content": section.content, "claims": section.claims,
        "verified_pct": section.verified_pct,
        "requirements_covered_pct": section.requirements_covered_pct,
        "style_match_pct": section.style_match_pct,
        "dropped_untagged": section.dropped_untagged,
        "approved": section.approved, "approved_by": section.approved_by,
        "open_flags": open_flags(section.claims or []),
    }
