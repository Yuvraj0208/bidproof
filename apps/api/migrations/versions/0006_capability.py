"""per-tenant capability database (SPEC §5.4, §15)

Revision ID: 0006
Revises: 0005

Two tables: company_facts and product_catalogue. Provenance is structural —
source and verified_at are NOT NULL on both, so a fact that cannot say where
it came from and when it was verified cannot be stored. product_code is the
external key that maps 1:1 onto SAP/PIM later.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

CURRENT_ORG = "NULLIF(current_setting('app.current_org_id', true), '')::uuid"

FACT_TYPES = (
    "turnover",
    "net_worth",
    "certification",
    "msme_status",
    "blacklist_status",
    "past_order",
)


def upgrade() -> None:
    op.create_table(
        "company_facts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fact_type", sa.String(), nullable=False),
        sa.Column("legal_entity", sa.String()),
        sa.Column("fiscal_year", sa.String()),
        sa.Column("value_text", sa.String()),
        sa.Column("value_number", sa.Numeric(16, 2)),
        sa.Column("unit", sa.String()),
        sa.Column("valid_until", sa.Date()),
        sa.Column("details", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("verified_at", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "fact_type IN " + str(FACT_TYPES), name="ck_company_facts_type"
        ),
        sa.CheckConstraint(
            "length(btrim(source)) > 0", name="ck_company_facts_provenance"
        ),
    )
    op.create_index("ix_company_facts_org_type", "company_facts", ["org_id", "fact_type"])

    op.create_table(
        "product_catalogue",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("product_code", sa.String(), nullable=False),
        sa.Column("product_name", sa.String(), nullable=False),
        sa.Column("category", sa.String()),
        sa.Column("specs", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("standards", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("lead_time_days", sa.Integer()),
        sa.Column("plant", sa.String()),
        sa.Column("capacity_per_month", sa.Integer()),
        sa.Column(
            "price_band_inr", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("verified_at", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("org_id", "product_code", name="uq_products_org_code"),
        sa.CheckConstraint(
            "length(btrim(product_name)) > 0", name="ck_products_name"
        ),
        sa.CheckConstraint(
            "length(btrim(source)) > 0", name="ck_products_provenance"
        ),
        sa.CheckConstraint(
            "lead_time_days IS NULL OR lead_time_days >= 0",
            name="ck_products_lead_time",
        ),
    )

    for table in ("company_facts", "product_catalogue"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_isolation ON {table}
            USING (org_id = {CURRENT_ORG})
            WITH CHECK (org_id = {CURRENT_ORG})
            """
        )
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO bidproof_app"
        )


def downgrade() -> None:
    op.drop_table("product_catalogue")
    op.drop_table("company_facts")
