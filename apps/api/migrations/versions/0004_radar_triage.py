"""org triage profiles + radar/triage fields on tenders (US-02)

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

CURRENT_ORG = "NULLIF(current_setting('app.current_org_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "org_profiles",
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "categories", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
        sa.Column("weights", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "value_band_inr", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column(
            "locations", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
        sa.Column(
            "win_categories", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.execute("ALTER TABLE org_profiles ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE org_profiles FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY org_profiles_isolation ON org_profiles
        USING (org_id = {CURRENT_ORG})
        WITH CHECK (org_id = {CURRENT_ORG})
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE ON org_profiles TO bidproof_app")

    op.add_column("tenders", sa.Column("radar_list", sa.String(), nullable=True))
    op.add_column("tenders", sa.Column("fit_score", sa.Float(), nullable=True))
    op.add_column("tenders", sa.Column("triage", postgresql.JSONB(), nullable=True))
    op.create_check_constraint(
        "ck_tenders_radar_list",
        "tenders",
        "radar_list IS NULL OR radar_list IN "
        "('in_our_lane','opportunity_radar','needs_human')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_tenders_radar_list", "tenders")
    op.drop_column("tenders", "triage")
    op.drop_column("tenders", "fit_score")
    op.drop_column("tenders", "radar_list")
    op.drop_table("org_profiles")
