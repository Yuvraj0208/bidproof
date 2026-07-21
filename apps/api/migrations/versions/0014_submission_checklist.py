"""submission checklist (US-18, SPEC §7 Checkpoint 6)

Revision ID: 0014
Revises: 0013

Every required document is an item. The system records the uploaded file's
format and whether it is signed; a human ticks each item, and nothing is
submit-ready until every required item is ticked (Checkpoint 6 never
auto-passes).
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

CURRENT_ORG = "NULLIF(current_setting('app.current_org_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "submission_items",
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
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("required_format", sa.String(), nullable=False),
        sa.Column("signature_required", sa.Boolean(), nullable=False,
                  server_default="true"),
        sa.Column("uploaded_format", sa.String()),
        sa.Column("signature_present", sa.Boolean()),
        sa.Column("ticked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("ticked_by", sa.String()),
        sa.Column("ticked_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("tender_id", "name", name="uq_submission_items"),
    )
    op.execute("ALTER TABLE submission_items ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE submission_items FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY submission_items_isolation ON submission_items
        USING (org_id = {CURRENT_ORG})
        WITH CHECK (org_id = {CURRENT_ORG})
        """
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON submission_items TO bidproof_app"
    )


def downgrade() -> None:
    op.drop_table("submission_items")
