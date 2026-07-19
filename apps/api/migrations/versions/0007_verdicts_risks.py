"""verdicts + risks (SPEC §5.5)

Revision ID: 0007
Revises: 0006

verdicts.rule_id is NOT NULL — the proof chain is unbroken by construction:
verdict -> rule -> element -> page+box.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

CURRENT_ORG = "NULLIF(current_setting('app.current_org_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "verdicts",
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
        sa.Column(
            "tender_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenders.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "rule_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("rules.rule_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("verdict", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("band", sa.String(), nullable=False),
        sa.Column("arithmetic", sa.Boolean(), nullable=False),
        sa.Column(
            "cited_fact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("company_facts.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "cited_product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("product_catalogue.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "verdict IN ('complies','partial','gap','not_applicable','needs_human')",
            name="ck_verdicts_verdict",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_verdicts_confidence"
        ),
        sa.CheckConstraint("band IN ('green','yellow','red')", name="ck_verdicts_band"),
        sa.UniqueConstraint("rule_id", name="uq_verdicts_rule"),
    )

    op.create_table(
        "risks",
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
        sa.Column(
            "tender_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenders.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("rupee_impact", sa.Numeric(14, 2)),
        sa.Column(
            "el_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("elements.el_id", ondelete="CASCADE"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "severity IN ('low','medium','high')", name="ck_risks_severity"
        ),
    )

    for table in ("verdicts", "risks"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_isolation ON {table}
            USING (org_id = {CURRENT_ORG})
            WITH CHECK (org_id = {CURRENT_ORG})
            """
        )
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO bidproof_app")


def downgrade() -> None:
    op.drop_table("risks")
    op.drop_table("verdicts")
