"""ORM models. Schema changes happen through Alembic migrations; these
classes mirror them for queries and future autogenerate support."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Tender(Base):
    __tablename__ = "tenders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False, server_default="manual")
    # Portal provenance (US-01). Dedup: unique (org, source, external_id).
    external_id: Mapped[str | None] = mapped_column(String)
    portal_url: Mapped[str | None] = mapped_column(String)
    closing_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Triage (US-02): list assignment + fit + the self-explaining breakdown.
    radar_list: Mapped[str | None] = mapped_column(String)
    fit_score: Mapped[float | None] = mapped_column(Float)
    triage: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OrgProfile(Base):
    __tablename__ = "org_profiles"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    categories: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    weights: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    value_band_inr: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    locations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    win_categories: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DiscoveryRun(Base):
    __tablename__ = "discovery_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    report: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("org_id", "sha256"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    bucket: Mapped[str] = mapped_column(String, nullable=False)
    object_key: Mapped[str] = mapped_column(String, nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    kind: Mapped[str] = mapped_column(
        String, nullable=False, server_default="original"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ParseRun(Base):
    __tablename__ = "parse_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String, nullable=False, server_default="pending"
    )
    pages_total: Mapped[int | None] = mapped_column(Integer)
    pages_text: Mapped[int | None] = mapped_column(Integer)
    pages_ocr: Mapped[int | None] = mapped_column(Integer)
    pages_flagged: Mapped[int | None] = mapped_column(Integer)
    elements_discarded: Mapped[int | None] = mapped_column(Integer)
    cost_inr: Mapped[float] = mapped_column(
        Numeric(12, 4), nullable=False, server_default="0"
    )
    trace_id: Mapped[str | None] = mapped_column(String)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Page(Base):
    __tablename__ = "pages"
    __table_args__ = (UniqueConstraint("document_id", "page_no"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    page_no: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[float] = mapped_column(Float, nullable=False)
    height: Mapped[float] = mapped_column(Float, nullable=False)
    route: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)


class CompanyFact(Base):
    """A verified fact about the company (SPEC §5.4). source + verified_at
    are NOT NULL — provenance is structural, like el_id on elements."""

    __tablename__ = "company_facts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fact_type: Mapped[str] = mapped_column(String, nullable=False)
    legal_entity: Mapped[str | None] = mapped_column(String)
    fiscal_year: Mapped[str | None] = mapped_column(String)
    value_text: Mapped[str | None] = mapped_column(String)
    value_number: Mapped[float | None] = mapped_column(Numeric(16, 2))
    unit: Mapped[str | None] = mapped_column(String)
    valid_until: Mapped[date | None] = mapped_column(Date)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    source: Mapped[str] = mapped_column(String, nullable=False)
    verified_at: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CatalogueProduct(Base):
    """One catalogue item. product_code is the external key that maps 1:1
    onto SAP/PIM when a real feed replaces manual entry."""

    __tablename__ = "product_catalogue"
    __table_args__ = (UniqueConstraint("org_id", "product_code"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_code: Mapped[str] = mapped_column(String, nullable=False)
    product_name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str | None] = mapped_column(String)
    specs: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    standards: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    lead_time_days: Mapped[int | None] = mapped_column(Integer)
    plant: Mapped[str | None] = mapped_column(String)
    capacity_per_month: Mapped[int | None] = mapped_column(Integer)
    price_band_inr: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    source: Mapped[str] = mapped_column(String, nullable=False)
    verified_at: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Rule(Base):
    """A grounded requirement rule (US-04). el_id is a NOT NULL foreign key
    into elements — a rule without proof cannot be stored (§9 rule 1)."""

    __tablename__ = "rules"

    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    family: Mapped[str] = mapped_column(String, nullable=False)
    key: Mapped[str] = mapped_column(String, nullable=False)
    requirement_text: Mapped[str] = mapped_column(Text, nullable=False)
    value_text: Mapped[str | None] = mapped_column(String)
    el_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("elements.el_id", ondelete="CASCADE"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(
        String, nullable=False, server_default="extracted"
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    band: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class VerdictRow(Base):
    """One verdict per rule (SPEC §5.5). rule_id NOT NULL keeps the proof
    chain unbroken: verdict -> rule -> element -> page+box."""

    __tablename__ = "verdicts"
    __table_args__ = (UniqueConstraint("rule_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rules.rule_id", ondelete="CASCADE"),
        nullable=False,
    )
    verdict: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    band: Mapped[str] = mapped_column(String, nullable=False)
    arithmetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    cited_fact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company_facts.id", ondelete="SET NULL")
    )
    cited_product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_catalogue.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RiskRow(Base):
    __tablename__ = "risks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)
    rupee_impact: Mapped[float | None] = mapped_column(Numeric(14, 2))
    el_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("elements.el_id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Decision(Base):
    """One decision per tender (US-06). Born pending_signoff — Checkpoint 4
    never auto-passes; a named human signs or overrides with a reason."""

    __tablename__ = "decisions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    recommendation: Mapped[str] = mapped_column(String, nullable=False)
    ev_inr: Mapped[float | None] = mapped_column(Numeric(16, 2))
    tender_value_inr: Mapped[float | None] = mapped_column(Numeric(16, 2))
    terms: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    gate_failed: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    band: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(
        String, nullable=False, server_default="pending_signoff"
    )
    signed_off_by: Mapped[str | None] = mapped_column(String)
    signed_off_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AuditLog(Base):
    """Append-only by grants: the app role can INSERT and SELECT, never
    UPDATE or DELETE (SPEC §14)."""

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    tender_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AgentRun(Base):
    """One recorded agent call (SPEC §13): the Agent Console's ledger."""

    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trace_id: Mapped[str] = mapped_column(String, nullable=False)
    agent: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="ok")
    model_role: Mapped[str | None] = mapped_column(String)
    prompt_version: Mapped[str | None] = mapped_column(String)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_inr: Mapped[float] = mapped_column(
        Numeric(12, 4), nullable=False, default=0
    )
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Amendment(Base):
    """One corrigendum's effect on a tender (US-07): the cited change list,
    the rules it affected/broke, and the EV before vs after."""

    __tablename__ = "amendments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(String, nullable=False)
    changes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    rules_affected: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    rules_broken: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    ev_before_inr: Mapped[float | None] = mapped_column(Numeric(16, 2))
    ev_after_inr: Mapped[float | None] = mapped_column(Numeric(16, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class QueryLetter(Base):
    """A drafted pre-bid query letter (US-08). Grounded to the rule it
    queries; the system only ever writes it as a draft (SPEC §5.8, §10)."""

    __tablename__ = "query_letters"
    __table_args__ = (UniqueConstraint("rule_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rules.rule_id", ondelete="CASCADE"),
        nullable=False,
    )
    el_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("elements.el_id", ondelete="CASCADE"),
        nullable=False,
    )
    rule_key: Mapped[str] = mapped_column(String, nullable=False)
    page_no: Mapped[int] = mapped_column(Integer, nullable=False)
    subject: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    query_deadline: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class LibraryBlockRow(Base):
    """A reusable proposal block (US-09). Quarantined by default — poisoning
    defence (SPEC §11.3); only approved blocks are ever retrieved."""

    __tablename__ = "library_blocks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_tag: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    source_name: Mapped[str] = mapped_column(String, nullable=False)
    quarantined: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Proposal(Base):
    __tablename__ = "proposals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="draft")
    format_source: Mapped[str] = mapped_column(
        String, nullable=False, server_default="default_template"
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ProposalSection(Base):
    __tablename__ = "proposal_sections"
    __table_args__ = (UniqueConstraint("proposal_id", "section_tag"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("proposals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_tag: Mapped[str] = mapped_column(String, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    claims: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    verified_pct: Mapped[float | None] = mapped_column(Float)
    requirements_covered_pct: Mapped[float | None] = mapped_column(Float)
    style_match_pct: Mapped[float | None] = mapped_column(Float)
    dropped_untagged: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    approved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    approved_by: Mapped[str | None] = mapped_column(String)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SubmissionItem(Base):
    """One required document on the submission checklist (US-18). The system
    records the uploaded format + signature; a human ticks each item."""

    __tablename__ = "submission_items"
    __table_args__ = (UniqueConstraint("tender_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    required_format: Mapped[str] = mapped_column(String, nullable=False)
    signature_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    uploaded_format: Mapped[str | None] = mapped_column(String)
    signature_present: Mapped[bool | None] = mapped_column(Boolean)
    ticked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    ticked_by: Mapped[str | None] = mapped_column(String)
    ticked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ChatMessage(Base):
    """One Ask-BidProof turn (US-15). Refusals and jailbreak attempts are
    recorded here and surface as a security metric (SPEC §11.2)."""

    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    refused: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    refusal_reason: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Element(Base):
    """A grounded piece of tender text. The schema makes ungrounded rows
    unrepresentable (§9 rule 1): text, box, page, and confidence are all
    constrained — see migration 0002 for the CHECKs."""

    __tablename__ = "elements"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "page_no"],
            ["pages.document_id", "pages.page_no"],
            ondelete="CASCADE",
        ),
    )

    el_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    page_no: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    x0: Mapped[float] = mapped_column(Float, nullable=False)
    y0: Mapped[float] = mapped_column(Float, nullable=False)
    x1: Mapped[float] = mapped_column(Float, nullable=False)
    y1: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    guard_flagged: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    guard_category: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
