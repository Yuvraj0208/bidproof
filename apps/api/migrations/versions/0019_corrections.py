"""corrections — the correction flywheel (US-20)

Revision ID: 0019
Revises: 0018

Every human correction of an extracted clause is recorded here. Only
corrections by reviewer-or-above roles are marked as labels (is_label) — a
junior or compromised account cannot quietly teach the system wrong answers
(SPEC §11.3, the poisoning defence). When the same clause type has been
corrected the same way twice, the next similar tender pre-fills it that way,
with a visible provenance note (§8 layer 4 — learned behaviour is never silent).
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None

CURRENT_ORG = "NULLIF(current_setting('app.current_org_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "corrections",
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
        ),
        # Informational: the rule that was corrected. Nullable + SET NULL so a
        # learned label survives even if that specific rule row is gone.
        sa.Column(
            "rule_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("rules.rule_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("family", sa.String(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("corrected_value", sa.Text(), nullable=False),
        sa.Column("corrected_by_role", sa.String(), nullable=False),
        sa.Column("corrected_by_name", sa.String(), nullable=False),
        sa.Column(
            "is_label", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(btrim(corrected_value)) > 0", name="ck_corrections_value"
        ),
    )
    # The pre-fill lookup is by (org, clause key) over labels only.
    op.create_index(
        "ix_corrections_org_key", "corrections", ["org_id", "key", "is_label"]
    )
    op.execute("ALTER TABLE corrections ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE corrections FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY corrections_isolation ON corrections
        USING (org_id = {CURRENT_ORG})
        WITH CHECK (org_id = {CURRENT_ORG})
        """
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON corrections TO bidproof_app"
    )


def downgrade() -> None:
    op.drop_table("corrections")
