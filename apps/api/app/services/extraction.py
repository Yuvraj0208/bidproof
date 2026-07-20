"""Extraction service (US-04): wires the Extractor agent to the DB and the
gateway. The pattern side always runs; the AI side goes through the gateway
role "mid" and degrades honestly when no model is reachable."""

import json
import logging
import re
import uuid

from sqlalchemy import delete, select

from bidproof_extractor import (
    CandidateRule,
    ElementRef,
    compare_and_merge,
    extract_pattern_rules,
    ground_check,
    parse_ai_response,
    resolve_vote,
)
from bidproof_extractor.prompts import EXTRACTOR_PROMPT_V1, VOTE_PROMPT_V1
from bidproof_extractor.schema import AiRule

from app.confidence import band_for
from app.core.db import org_scoped_session
from app.llm.gateway import LLMGateway
from app.models import Document, Element, Rule

logger = logging.getLogger(__name__)

MAX_ELEMENT_CHARS = 24000
SCHEMA_RETRIES = 1


def get_extraction_gateway() -> LLMGateway:
    return LLMGateway()


def build_elements_block(refs: list[ElementRef]) -> str:
    """Fenced data block (§11.1): document text is data, never instructions."""
    lines, used = [], 0
    for ref in refs:
        line = f"[{ref.el_id}] page {ref.page_no}: {ref.text}"
        used += len(line)
        if used > MAX_ELEMENT_CHARS:
            break
        lines.append(line)
    return "<tender_elements>\n" + "\n".join(lines) + "\n</tender_elements>"


async def _call_model(
    gateway: LLMGateway, system: str, user: str, usage: dict | None = None
) -> str | None:
    try:
        response = await gateway.complete(
            "mid",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0,
        )
        if usage is not None and isinstance(response.get("usage"), dict):
            usage["in"] = usage.get("in", 0) + int(response["usage"].get("prompt_tokens", 0))
            usage["out"] = usage.get("out", 0) + int(response["usage"].get("completion_tokens", 0))
        return response["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.warning("extractor model call failed: %s", exc)
        return None


async def _ai_extract(
    gateway: LLMGateway, refs: list[ElementRef], usage: dict | None = None
) -> tuple[list[AiRule], str | None]:
    block = build_elements_block(refs)
    for _attempt in range(1 + SCHEMA_RETRIES):
        raw = await _call_model(gateway, EXTRACTOR_PROMPT_V1, block, usage)
        if raw is None:
            return [], "model unavailable — pattern extraction only"
        parsed = parse_ai_response(raw)
        if parsed is not None:
            return parsed.rules, None
    return [], "model output rejected by schema — pattern extraction only"


_VOTE_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _parse_vote(raw: str) -> str | None:
    """Strict single-field parse; anything malformed is a non-vote."""
    text = raw.strip()
    fenced = _VOTE_FENCE.search(text)
    if fenced:
        text = fenced.group(1).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    value = payload.get("value") if isinstance(payload, dict) else None
    return value if isinstance(value, str) else None


async def _vote_values(
    gateway: LLMGateway, refs: list[ElementRef], key: str
) -> list[str | None]:
    block = build_elements_block(refs)
    values: list[str | None] = []
    for _ in range(3):
        raw = await _call_model(gateway, VOTE_PROMPT_V1.format(key=key), block)
        if raw is not None:
            values.append(_parse_vote(raw))
    return values


async def build_candidate_rules(
    refs: list[ElementRef], gateway: LLMGateway | None, usage: dict | None = None
) -> tuple[list[CandidateRule], int, str | None]:
    """The dual-extractor core (pattern + cited AI + compare + vote), grounded
    to the given elements. Returns (merged rules, discarded_uncited, note).
    Shared by full extraction and the Amendment Watcher — no persistence."""
    by_id = {r.el_id: r for r in refs}
    pattern_rules = extract_pattern_rules(refs)

    ai_note: str | None = None
    grounded_ai: list[CandidateRule] = []
    discarded = 0
    if gateway is not None:
        ai_rules, ai_note = await _ai_extract(gateway, refs, usage)
        grounded_ai, discarded = ground_check(ai_rules, by_id)

    merged, disputes = compare_and_merge(pattern_rules, grounded_ai)
    for pattern_rule, _ai_rule in disputes:
        votes = (
            await _vote_values(gateway, refs, pattern_rule.key) if gateway else []
        )
        merged.append(resolve_vote(pattern_rule, votes))
    return merged, discarded, ai_note


async def extract_rules(
    org_id: uuid.UUID, tender_id: uuid.UUID, gateway: LLMGateway | None = None
) -> dict | None:
    import time

    from app.core.config import get_settings
    from app.observability import record_agent_run

    started = time.monotonic()
    usage: dict = {}
    async with org_scoped_session(org_id) as session:
        document = (
            await session.execute(
                select(Document)
                .where(Document.tender_id == tender_id)
                .order_by(Document.version.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if document is None:
            return None
        rows = (
            await session.execute(
                select(Element)
                .where(Element.document_id == document.id)
                .order_by(Element.page_no, Element.seq)
            )
        ).scalars()
        refs = [
            ElementRef(el_id=str(e.el_id), page_no=e.page_no, text=e.text)
            for e in rows
        ]

    if not refs:
        return {"rules": 0, "note": "no parsed elements to extract from"}

    merged, discarded, ai_note = await build_candidate_rules(refs, gateway, usage)

    async with org_scoped_session(org_id) as session:
        await session.execute(delete(Rule).where(Rule.document_id == document.id))
        for rule in merged:
            session.add(
                Rule(
                    org_id=org_id,
                    tender_id=tender_id,
                    document_id=document.id,
                    family=rule.family,
                    key=rule.key,
                    requirement_text=rule.requirement_text,
                    value_text=rule.value,
                    el_id=uuid.UUID(rule.el_id),
                    source=rule.source,
                    status=rule.status,
                    confidence=rule.confidence,
                    band=band_for(rule.confidence),
                    reason=rule.reason,
                )
            )

    tokens_in, tokens_out = usage.get("in", 0), usage.get("out", 0)
    cost_inr = round(
        (tokens_in + tokens_out) / 1000 * get_settings().llm_cost_per_1k_tokens_inr, 4
    )
    await record_agent_run(
        org_id, tender_id, "extractor",
        duration_ms=int((time.monotonic() - started) * 1000),
        model_role="mid" if gateway is not None else None,
        prompt_version="extractor_v1" if gateway is not None else None,
        tokens_in=tokens_in, tokens_out=tokens_out, cost_inr=cost_inr,
        meta={"rules": len(merged), "discarded_uncited": discarded,
              "note": ai_note},
    )
    return {
        "rules": len(merged),
        "needs_human": sum(1 for r in merged if r.status == "needs_human"),
        "discarded_uncited": discarded,
        "sources": {
            s: sum(1 for r in merged if r.source == s)
            for s in ("pattern", "ai", "both", "vote")
        },
        "note": ai_note,
    }


async def extract_after_parse(org_id: uuid.UUID, tender_id: uuid.UUID) -> None:
    """Post-parse hook: extraction must never take ingestion down."""
    try:
        await extract_rules(org_id, tender_id, gateway=get_extraction_gateway())
    except Exception:
        logger.exception("extraction failed for tender %s", tender_id)
