"""FormFiller service (SPEC §5.8): build a value context from the capability
database — verified company facts only — and fill the standard declarations.

Anything the capability DB cannot supply is left blank and flagged. The
service never invents a value; the ProposalWriter's rule applies here too —
facts come from the database, and nothing else."""

import uuid

from sqlalchemy import select

from bidproof_formfiller import (
    STANDARD_DECLARATIONS,
    fill_declaration,
    template_by_id,
)

from app.core.db import org_scoped_session
from app.models import CompanyFact, Organization


def _crore(value: float | None) -> str | None:
    return None if value is None else f"₹{value / 1e7:.2f} crore"


async def build_context(org_id: uuid.UUID) -> dict[str, str | None]:
    """Every value here comes from a verified capability fact (or the org
    record). Sources we cannot supply are simply absent — the FormFiller
    flags them. We deliberately do NOT fill signatory / place / date, because
    signing a declaration is a human act, not a company fact."""
    async with org_scoped_session(org_id) as session:
        org = await session.get(Organization, org_id)
        facts = (await session.execute(select(CompanyFact))).scalars().all()

    by_type: dict[str, list[CompanyFact]] = {}
    for fact in facts:
        by_type.setdefault(fact.fact_type, []).append(fact)

    def latest_turnover() -> str | None:
        turnovers = [f for f in by_type.get("turnover", []) if f.value_number is not None]
        if not turnovers:
            return None
        newest = max(turnovers, key=lambda f: f.fiscal_year or "")
        amount = _crore(float(newest.value_number))
        return f"{amount} (FY {newest.fiscal_year})" if newest.fiscal_year else amount

    def net_worth() -> str | None:
        rows = [f for f in by_type.get("net_worth", []) if f.value_number is not None]
        return _crore(float(rows[0].value_number)) if rows else None

    def single(fact_type: str) -> str | None:
        rows = by_type.get(fact_type, [])
        return rows[0].value_text if rows and rows[0].value_text else None

    def company_legal_name() -> str | None:
        for fact in by_type.get("turnover", []):
            if fact.legal_entity:
                return fact.legal_entity
        return org.name if org else None

    blacklist = single("blacklist_status")
    if blacklist and blacklist.lower() in ("none", "not blacklisted", "no"):
        blacklist = "Not blacklisted by any government agency"

    return {
        "company_legal_name": company_legal_name(),
        "latest_turnover": latest_turnover(),
        "net_worth": net_worth(),
        "msme_status": single("msme_status"),
        "blacklist_status": blacklist,
        # Human-only fields — intentionally absent so they are flagged.
        "authorised_signatory": None,
        "signatory_designation": None,
        "registered_office": None,
        "place": None,
        "declaration_date": None,
    }


def _serialise(declaration) -> dict:
    return {
        "template_id": declaration.template_id,
        "title": declaration.title,
        "complete": declaration.complete,
        "flagged_count": declaration.flagged_count,
        "fields": [
            {
                "key": f.key, "label": f.label, "value": f.value,
                "filled": f.filled, "flagged": f.flagged,
                "source": f.source, "reason": f.reason,
            }
            for f in declaration.fields
        ],
    }


async def fill_all(org_id: uuid.UUID) -> list[dict]:
    context = await build_context(org_id)
    return [_serialise(fill_declaration(t, context)) for t in STANDARD_DECLARATIONS]


async def fill_one(org_id: uuid.UUID, template_id: str) -> dict | None:
    template = template_by_id(template_id)
    if template is None:
        return None
    context = await build_context(org_id)
    return _serialise(fill_declaration(template, context))
