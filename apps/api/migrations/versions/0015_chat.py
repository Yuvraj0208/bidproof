"""ask-bidproof chat log (US-15, SPEC §8.3, §11.2)

Revision ID: 0015
Revises: 0014

Every turn is recorded — including refusals and jailbreak attempts, which
show up as a security metric in the Admin dashboard.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

CURRENT_ORG = "NULLIF(current_setting('app.current_org_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "chat_messages",
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
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("refused", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("refusal_reason", sa.String()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("role IN ('user','assistant')", name="ck_chat_role"),
    )
    op.execute("ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE chat_messages FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY chat_messages_isolation ON chat_messages
        USING (org_id = {CURRENT_ORG})
        WITH CHECK (org_id = {CURRENT_ORG})
        """
    )
    op.execute("GRANT SELECT, INSERT ON chat_messages TO bidproof_app")


def downgrade() -> None:
    op.drop_table("chat_messages")
