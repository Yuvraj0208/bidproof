"""portal discovery: tender source metadata + dedup index + discovery runs

Revision ID: 0003
Revises: 0002

Dedup contract (US-01): within an org, a portal tender exists once —
unique (org_id, source, external_id). Content-level dedup by document
sha256 already exists from 0002.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

CURRENT_ORG = "NULLIF(current_setting('app.current_org_id', true), '')::uuid"


def upgrade() -> None:
    op.add_column("tenders", sa.Column("external_id", sa.String(), nullable=True))
    op.add_column("tenders", sa.Column("portal_url", sa.String(), nullable=True))
    op.add_column(
        "tenders", sa.Column("closing_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        "uq_tenders_org_source_external",
        "tenders",
        ["org_id", "source", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )

    op.create_table(
        "discovery_runs",
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
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("report", postgresql.JSONB(), nullable=False, server_default="{}"),
    )
    op.execute("ALTER TABLE discovery_runs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE discovery_runs FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY discovery_runs_isolation ON discovery_runs
        USING (org_id = {CURRENT_ORG})
        WITH CHECK (org_id = {CURRENT_ORG})
        """
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON discovery_runs TO bidproof_app"
    )


def downgrade() -> None:
    op.drop_table("discovery_runs")
    op.drop_index("uq_tenders_org_source_external", table_name="tenders")
    op.drop_column("tenders", "closing_at")
    op.drop_column("tenders", "portal_url")
    op.drop_column("tenders", "external_id")
