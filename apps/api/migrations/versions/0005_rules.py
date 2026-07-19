"""rules — grounded requirement rules (US-04)

Revision ID: 0005
Revises: 0004

The load-bearing constraint: el_id is NOT NULL and a FOREIGN KEY into
elements. A rule that cannot point at a real page+box is unrepresentable
(§9 rule 1) — thrown away upstream, impossible downstream.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

CURRENT_ORG = "NULLIF(current_setting('app.current_org_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "rules",
        sa.Column(
            "rule_id",
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
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("family", sa.String(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("requirement_text", sa.Text(), nullable=False),
        sa.Column("value_text", sa.String()),
        sa.Column(
            "el_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("elements.el_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="extracted"),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("band", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "family IN ('eligibility','technical','commercial','legal','submission')",
            name="ck_rules_family",
        ),
        sa.CheckConstraint(
            "source IN ('pattern','ai','both','vote')", name="ck_rules_source"
        ),
        sa.CheckConstraint(
            "status IN ('extracted','needs_human')", name="ck_rules_status"
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_rules_confidence"
        ),
        sa.CheckConstraint(
            "band IN ('green','yellow','red')", name="ck_rules_band"
        ),
        sa.CheckConstraint(
            "length(btrim(requirement_text)) > 0", name="ck_rules_text"
        ),
    )
    op.create_index("ix_rules_document_id", "rules", ["document_id"])
    op.execute("ALTER TABLE rules ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE rules FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY rules_isolation ON rules
        USING (org_id = {CURRENT_ORG})
        WITH CHECK (org_id = {CURRENT_ORG})
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON rules TO bidproof_app")


def downgrade() -> None:
    op.drop_table("rules")
