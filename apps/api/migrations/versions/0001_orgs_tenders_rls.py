"""organizations + tenders with row-level security (SPEC §15)

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# Absent org context reads as NULL and matches nothing: fail closed.
CURRENT_ORG = "NULLIF(current_setting('app.current_org_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_table(
        "tenders",
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
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False, server_default="manual"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_tenders_org_id", "tenders", ["org_id"])

    # FORCE so even the table owner cannot bypass; the app connects as
    # bidproof_app, which has no BYPASSRLS.
    for table in ("organizations", "tenders"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    op.execute(
        f"""
        CREATE POLICY org_isolation ON organizations
        FOR SELECT USING (id = {CURRENT_ORG})
        """
    )
    op.execute(
        f"""
        CREATE POLICY tender_isolation ON tenders
        USING (org_id = {CURRENT_ORG})
        WITH CHECK (org_id = {CURRENT_ORG})
        """
    )

    # Least privilege: the app role gets no DDL and cannot create
    # organizations (that is an owner/onboarding operation).
    op.execute("GRANT SELECT ON organizations TO bidproof_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON tenders TO bidproof_app")


def downgrade() -> None:
    op.drop_table("tenders")
    op.drop_table("organizations")
