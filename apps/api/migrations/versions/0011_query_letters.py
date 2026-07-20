"""query_letters — the pre-bid question pack (US-08, SPEC §5.8)

Revision ID: 0011
Revises: 0010

Each letter is grounded to the rule it queries (rule_id NOT NULL FK), so the
proof chain holds: letter -> rule -> element -> page+box. There is no 'sent'
state written by the system — drafts only (least privilege, SPEC §10).
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

CURRENT_ORG = "NULLIF(current_setting('app.current_org_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "query_letters",
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
        sa.Column(
            "el_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("elements.el_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rule_key", sa.String(), nullable=False),
        sa.Column("page_no", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("query_deadline", sa.Date()),
        # 'draft' is the only value the system writes. A human may record that
        # they sent it, but the system never sends.
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('draft','marked_sent_by_human')", name="ck_query_letters_status"
        ),
        sa.CheckConstraint(
            "length(btrim(body)) > 0", name="ck_query_letters_body"
        ),
        sa.UniqueConstraint("rule_id", name="uq_query_letters_rule"),
    )
    op.execute("ALTER TABLE query_letters ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE query_letters FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY query_letters_isolation ON query_letters
        USING (org_id = {CURRENT_ORG})
        WITH CHECK (org_id = {CURRENT_ORG})
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON query_letters TO bidproof_app")


def downgrade() -> None:
    op.drop_table("query_letters")
