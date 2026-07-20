"""library_blocks + proposals + proposal_sections (US-09, SPEC §5.7)

Revision ID: 0012
Revises: 0011

library_blocks are quarantined by default (poisoning defence, SPEC §11.3).
proposal_sections carry per-claim verification results and the `approved`
flag US-11 will gate on.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

CURRENT_ORG = "NULLIF(current_setting('app.current_org_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "library_blocks",
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
        sa.Column("section_tag", sa.String(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("source_name", sa.String(), nullable=False),
        sa.Column(
            "quarantined", sa.Boolean(), nullable=False, server_default="true"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "outcome IN ('won','lost','synthetic')", name="ck_library_outcome"
        ),
        sa.CheckConstraint("length(btrim(text)) > 0", name="ck_library_text"),
        sa.CheckConstraint(
            "length(btrim(source_name)) > 0", name="ck_library_provenance"
        ),
    )

    op.create_table(
        "proposals",
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
            unique=True,
        ),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column(
            "format_source", sa.String(), nullable=False,
            server_default="default_template",
        ),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "format_source IN ('default_template','tender_dictated')",
            name="ck_proposals_format",
        ),
    )

    op.create_table(
        "proposal_sections",
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
            "proposal_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("proposals.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("section_tag", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("claims", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("verified_pct", sa.Float()),
        sa.Column("dropped_untagged", sa.Integer(), nullable=False,
                  server_default="0"),
        sa.Column("approved", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("proposal_id", "section_tag",
                            name="uq_proposal_sections"),
    )

    for table in ("library_blocks", "proposals", "proposal_sections"):
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
    op.drop_table("proposal_sections")
    op.drop_table("proposals")
    op.drop_table("library_blocks")
