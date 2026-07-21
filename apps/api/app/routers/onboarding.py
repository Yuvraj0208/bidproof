"""Onboarding wizard endpoints (US-17, SPEC §15). Create an org, upload the
company facts and product catalogue (CSV), pick categories + weights, add
branding, finish. No developer required."""

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field

from app.core.tenancy import require_org_id
from app.services import onboarding

router = APIRouter()


class CreateOrgIn(BaseModel):
    name: str = Field(min_length=2)
    slug: str = Field(min_length=2, pattern=r"^[a-z0-9-]+$")


class ProfileIn(BaseModel):
    categories: list[dict] = Field(default_factory=list)
    weights: dict = Field(default_factory=dict)
    value_band_inr: dict = Field(default_factory=dict)
    locations: list[str] = Field(default_factory=list)
    win_categories: list[str] = Field(default_factory=list)


class BrandingIn(BaseModel):
    primary_color: str | None = None
    logo_url: str | None = None
    finish: bool = False


@router.post("/onboarding/org", status_code=201)
async def create_org(body: CreateOrgIn) -> dict:
    """Provision a new tenant. This is the one open step; everything after is
    scoped to the returned org id."""
    org_id = await onboarding.create_org(body.name.strip(), body.slug.strip())
    if org_id is None:
        raise HTTPException(409, f"an organization with slug {body.slug!r} exists")
    return {"org_id": str(org_id), "name": body.name, "slug": body.slug}


@router.get("/onboarding/templates/products.csv")
async def products_template() -> Response:
    return Response(content=onboarding.PRODUCT_CSV_TEMPLATE, media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="products.csv"'})


@router.get("/onboarding/templates/facts.csv")
async def facts_template() -> Response:
    return Response(content=onboarding.FACT_CSV_TEMPLATE, media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="facts.csv"'})


@router.post("/onboarding/facts")
async def upload_facts(
    file: UploadFile = File(...),
    org_id: uuid.UUID = Depends(require_org_id),
) -> dict:
    content = (await file.read()).decode("utf-8", errors="ignore")
    count = await onboarding.load_facts_csv(org_id, content,
                                            source=f"onboarding upload: {file.filename}")
    return {"facts_loaded": count}


@router.post("/onboarding/products")
async def upload_products(
    file: UploadFile = File(...),
    org_id: uuid.UUID = Depends(require_org_id),
) -> dict:
    content = (await file.read()).decode("utf-8", errors="ignore")
    count = await onboarding.load_products_csv(org_id, content,
                                               source=f"onboarding upload: {file.filename}")
    return {"products_loaded": count}


@router.post("/onboarding/profile")
async def set_profile(
    body: ProfileIn, org_id: uuid.UUID = Depends(require_org_id)
) -> dict:
    await onboarding.set_profile(
        org_id, body.categories, body.weights, body.value_band_inr,
        body.locations, body.win_categories,
    )
    return {"profile": "saved"}


@router.post("/onboarding/branding")
async def set_branding(
    body: BrandingIn, org_id: uuid.UUID = Depends(require_org_id)
) -> dict:
    branding = {k: v for k, v in
                {"primary_color": body.primary_color, "logo_url": body.logo_url}.items()
                if v}
    await onboarding.set_branding(org_id, branding, mark_done=body.finish)
    return {"branding": "saved", "onboarded": body.finish}


@router.get("/onboarding/status")
async def status(org_id: uuid.UUID = Depends(require_org_id)) -> dict:
    result = await onboarding.status(org_id)
    if result is None:
        raise HTTPException(404, "org not found")
    return result
