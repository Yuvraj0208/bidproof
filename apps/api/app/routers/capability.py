"""Capability database endpoints (SPEC §5.4). The Rule Checker reads these;
the onboarding wizard (US-17) becomes the proper write path later. Every
write must carry provenance — the API rejects what the schema would anyway."""

import uuid
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.db import org_scoped_session
from app.core.tenancy import require_org_id
from app.models import CatalogueProduct, CompanyFact

router = APIRouter()

FactType = Literal[
    "turnover",
    "net_worth",
    "certification",
    "msme_status",
    "blacklist_status",
    "past_order",
]


class FactIn(BaseModel):
    fact_type: FactType
    legal_entity: str | None = None
    fiscal_year: str | None = None
    value_text: str | None = None
    value_number: float | None = None
    unit: str | None = None
    valid_until: date | None = None
    details: dict = Field(default_factory=dict)
    source: str = Field(min_length=3)
    verified_at: date


class FactOut(FactIn):
    id: uuid.UUID
    created_at: datetime


class ProductIn(BaseModel):
    product_code: str = Field(min_length=1)
    product_name: str = Field(min_length=1)
    category: str | None = None
    specs: dict = Field(default_factory=dict)
    standards: list[str] = Field(default_factory=list)
    lead_time_days: int | None = Field(default=None, ge=0)
    plant: str | None = None
    capacity_per_month: int | None = Field(default=None, ge=0)
    price_band_inr: dict = Field(default_factory=dict)
    source: str = Field(min_length=3)
    verified_at: date


class ProductOut(ProductIn):
    id: uuid.UUID
    created_at: datetime


@router.get("/capability/facts", response_model=list[FactOut])
async def list_facts(
    fact_type: FactType | None = None,
    org_id: uuid.UUID = Depends(require_org_id),
) -> list[FactOut]:
    async with org_scoped_session(org_id) as session:
        query = select(CompanyFact).order_by(CompanyFact.created_at)
        if fact_type:
            query = query.where(CompanyFact.fact_type == fact_type)
        rows = (await session.execute(query)).scalars()
        return [FactOut.model_validate(r, from_attributes=True) for r in rows]


@router.post("/capability/facts", response_model=FactOut, status_code=201)
async def create_fact(
    body: FactIn, org_id: uuid.UUID = Depends(require_org_id)
) -> FactOut:
    async with org_scoped_session(org_id) as session:
        fact = CompanyFact(org_id=org_id, **body.model_dump())
        session.add(fact)
        await session.flush()
        return FactOut.model_validate(fact, from_attributes=True)


@router.get("/capability/products", response_model=list[ProductOut])
async def list_products(
    org_id: uuid.UUID = Depends(require_org_id),
) -> list[ProductOut]:
    async with org_scoped_session(org_id) as session:
        rows = (
            await session.execute(
                select(CatalogueProduct).order_by(CatalogueProduct.product_code)
            )
        ).scalars()
        return [ProductOut.model_validate(r, from_attributes=True) for r in rows]


@router.post("/capability/products", response_model=ProductOut, status_code=201)
async def create_product(
    body: ProductIn, org_id: uuid.UUID = Depends(require_org_id)
) -> ProductOut:
    try:
        async with org_scoped_session(org_id) as session:
            product = CatalogueProduct(org_id=org_id, **body.model_dump())
            session.add(product)
            await session.flush()
            return ProductOut.model_validate(product, from_attributes=True)
    except IntegrityError:
        raise HTTPException(
            409, f"product_code {body.product_code!r} already exists for this org"
        )
