"""decisions + append-only audit log (US-06, SPEC §5.6, §14)

Revision ID: 0008
Revises: 0007

audit_log is append-only for the application: bidproof_app receives ONLY
SELECT and INSERT — UPDATE and DELETE are not granted, so editing history
is a permission error, not a policy hope.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

CURRENT_ORG = "NULLIF(current_setting('app.current_org_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "decisions",
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
        sa.Column("recommendation", sa.String(), nullable=False),
        sa.Column("ev_inr", sa.Numeric(16, 2)),
        sa.Column("terms", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("gate_failed", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("band", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending_signoff"),
        sa.Column("signed_off_by", sa.String()),
        sa.Column("signed_off_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "recommendation IN ('go','no_go','needs_human')",
            name="ck_decisions_recommendation",
        ),
        sa.CheckConstraint(
            "status IN ('pending_signoff','signed_off','overridden')",
            name="ck_decisions_status",
        ),
        sa.CheckConstraint("band IN ('green','yellow','red')", name="ck_decisions_band"),
    )
    op.execute("ALTER TABLE decisions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE decisions FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY decisions_isolation ON decisions
        USING (org_id = {CURRENT_ORG})
        WITH CHECK (org_id = {CURRENT_ORG})
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE ON decisions TO bidproof_app")

    op.create_table(
        "audit_log",
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
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("tender_id", postgresql.UUID(as_uuid=True)),
        sa.Column("details", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("length(btrim(actor)) > 0", name="ck_audit_actor"),
    )
    op.execute("ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_log FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY audit_log_isolation ON audit_log
        USING (org_id = {CURRENT_ORG})
        WITH CHECK (org_id = {CURRENT_ORG})
        """
    )
    # Append-only: SELECT + INSERT and nothing else.
    op.execute("GRANT SELECT, INSERT ON audit_log TO bidproof_app")


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("decisions")
