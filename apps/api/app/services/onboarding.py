"""Onboarding wizard (US-17, SPEC §15): create an org, load its company
facts and product catalogue (CSV), pick categories + weights, add branding —
a new company live in under an hour, no developer. Every org is isolated by
row-level security from the moment it is created."""

import csv
import io
import re
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.core.db import org_scoped_session
from app.models import (
    CatalogueProduct,
    CompanyFact,
    Organization,
    OrgProfile,
)

PRODUCT_CSV_TEMPLATE = (
    "product_code,product_name,category,standards,lead_time_days,plant,"
    "capacity_per_month,price_min_inr,price_max_inr\n"
    "RACK-HD-01,Heavy-duty pallet rack,storage racks,IS 4923|ISO 9001,45,"
    "Plant 1,500,18000,42000\n"
)

FACT_CSV_TEMPLATE = (
    "fact_type,legal_entity,fiscal_year,value_text,value_number,unit,valid_until\n"
    "turnover,Acme Pvt Ltd,2024-25,,150000000,inr,\n"
    "certification,,,ISO 9001:2015,,,2027-08-31\n"
    "msme_status,,,not_msme,,,\n"
)


async def create_org(name: str, slug: str) -> uuid.UUID | None:
    """Provision a new tenant. Creating an organization is a privileged act
    (the app role cannot, by RLS) so it runs on the owner engine — the ONLY
    thing that does. Everything after is RLS-scoped to the new org."""
    engine = create_async_engine(get_settings().database_url_owner)
    try:
        async with engine.connect() as conn:
            exists = (
                await conn.execute(
                    text("SELECT id FROM organizations WHERE slug = :s"), {"s": slug}
                )
            ).first()
            if exists:
                return None
            org_id = uuid.uuid4()
            await conn.execute(
                text("INSERT INTO organizations (id, name, slug) "
                     "VALUES (:i, :n, :s)"),
                {"i": org_id, "n": name, "s": slug},
            )
            await conn.commit()
            return org_id
    finally:
        await engine.dispose()


def _num(value: str) -> float | None:
    value = (value or "").strip().replace(",", "")
    try:
        return float(value) if value else None
    except ValueError:
        return None


def _parse_date(value: str) -> date | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


async def load_facts_csv(org_id: uuid.UUID, content: str, source: str) -> int:
    reader = csv.DictReader(io.StringIO(content))
    inserted = 0
    async with org_scoped_session(org_id) as session:
        for row in reader:
            fact_type = (row.get("fact_type") or "").strip()
            if not fact_type:
                continue
            session.add(CompanyFact(
                org_id=org_id, fact_type=fact_type,
                legal_entity=(row.get("legal_entity") or "").strip() or None,
                fiscal_year=(row.get("fiscal_year") or "").strip() or None,
                value_text=(row.get("value_text") or "").strip() or None,
                value_number=_num(row.get("value_number", "")),
                unit=(row.get("unit") or "").strip() or None,
                valid_until=_parse_date(row.get("valid_until", "")),
                source=source, verified_at=date.today(),
            ))
            inserted += 1
    return inserted


async def load_products_csv(org_id: uuid.UUID, content: str, source: str) -> int:
    reader = csv.DictReader(io.StringIO(content))
    inserted = 0
    async with org_scoped_session(org_id) as session:
        for row in reader:
            code = (row.get("product_code") or "").strip()
            name = (row.get("product_name") or "").strip()
            if not code or not name:
                continue
            standards = [s for s in re.split(r"[|;,]", row.get("standards", ""))
                         if s.strip()]
            price = {}
            if _num(row.get("price_min_inr", "")) is not None:
                price["min_inr"] = _num(row["price_min_inr"])
            if _num(row.get("price_max_inr", "")) is not None:
                price["max_inr"] = _num(row["price_max_inr"])
            session.add(CatalogueProduct(
                org_id=org_id, product_code=code, product_name=name,
                category=(row.get("category") or "").strip() or None,
                standards=[s.strip() for s in standards],
                lead_time_days=int(_num(row.get("lead_time_days", "")))
                if _num(row.get("lead_time_days", "")) is not None else None,
                plant=(row.get("plant") or "").strip() or None,
                capacity_per_month=int(_num(row.get("capacity_per_month", "")))
                if _num(row.get("capacity_per_month", "")) is not None else None,
                price_band_inr=price,
                source=source, verified_at=date.today(),
            ))
            inserted += 1
    return inserted


async def set_profile(org_id: uuid.UUID, categories, weights, value_band,
                      locations, win_categories) -> None:
    async with org_scoped_session(org_id) as session:
        profile = await session.get(OrgProfile, org_id)
        if profile is None:
            profile = OrgProfile(org_id=org_id)
            session.add(profile)
        profile.categories = categories or []
        profile.weights = weights or {}
        profile.value_band_inr = value_band or {}
        profile.locations = locations or []
        profile.win_categories = win_categories or []


async def set_branding(org_id: uuid.UUID, branding: dict, mark_done: bool) -> None:
    """Branding + the onboarded flag live on the shared organizations table,
    which the app role may only read (least privilege). Writing them is a
    provisioning step, so it runs on the owner engine — like org creation."""
    import json as _json

    engine = create_async_engine(get_settings().database_url_owner)
    try:
        async with engine.connect() as conn:
            if mark_done:
                await conn.execute(
                    text("UPDATE organizations SET branding = CAST(:b AS jsonb), "
                         "onboarded_at = :t WHERE id = :i"),
                    {"b": _json.dumps(branding or {}),
                     "t": datetime.now(timezone.utc), "i": org_id},
                )
            else:
                await conn.execute(
                    text("UPDATE organizations SET branding = CAST(:b AS jsonb) "
                         "WHERE id = :i"),
                    {"b": _json.dumps(branding or {}), "i": org_id},
                )
            await conn.commit()
    finally:
        await engine.dispose()


async def status(org_id: uuid.UUID) -> dict | None:
    async with org_scoped_session(org_id) as session:
        org = await session.get(Organization, org_id)
        if org is None:
            return None
        facts = (await session.execute(select(CompanyFact.id))).scalars().all()
        products = (await session.execute(select(CatalogueProduct.id))).scalars().all()
        profile = await session.get(OrgProfile, org_id)
    steps = {
        "org": True,
        "facts": len(facts) > 0,
        "products": len(products) > 0,
        "profile": profile is not None and bool(profile.categories),
        "branding": bool(org.branding),
    }
    return {
        "org_id": str(org_id), "name": org.name, "slug": org.slug,
        "steps": steps,
        "facts": len(facts), "products": len(products),
        "onboarded": org.onboarded_at is not None,
        "ready": steps["facts"] and steps["products"] and steps["profile"],
    }


async def list_orgs() -> list[dict]:
    """Every organisation, for the sign-in company picker.

    Runs on the owner engine: choosing a workspace happens before any org
    context exists, so an RLS-scoped session cannot answer it. Only identity and
    branding are returned — never anything a tenant owns.
    """
    engine = create_async_engine(get_settings().database_url_owner)
    try:
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text("SELECT id, name, slug, branding, onboarded_at "
                         "FROM organizations ORDER BY name")
                )
            ).all()
    finally:
        await engine.dispose()
    return [
        {
            "org_id": row.id,
            "name": row.name,
            "slug": row.slug,
            "branding": row.branding or {},
            "onboarded": row.onboarded_at is not None,
        }
        for row in rows
    ]
