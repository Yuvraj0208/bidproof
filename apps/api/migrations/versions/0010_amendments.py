"""document versioning + amendments (US-07, SPEC §5.1 Amendment Watcher)

Revision ID: 0010
Revises: 0009

A tender can now carry more than one document over its life: the original
plus corrigenda. `version` orders them; the highest version is current.
`amendments` records each corrigendum's diff, the rules it affected, and
the EV before/after — the precise, cited alert.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

CURRENT_ORG = "NULLIF(current_setting('app.current_org_id', true), '')::uuid"


def upgrade() -> None:
    # The tender value the EV was computed from — stable across corrigenda
    # (a corrigendum carries no contract value, so recomputation reuses this).
    op.add_column(
        "decisions", sa.Column("tender_value_inr", sa.Numeric(16, 2))
    )
    op.add_column(
        "documents",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "documents",
        sa.Column("kind", sa.String(), nullable=False, server_default="original"),
    )
    op.create_check_constraint(
        "ck_documents_kind", "documents", "kind IN ('original','corrigendum')"
    )

    op.create_table(
        "amendments",
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
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("changes", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("rules_affected", postgresql.JSONB(), nullable=False,
                  server_default="[]"),
        sa.Column("rules_broken", postgresql.JSONB(), nullable=False,
                  server_default="[]"),
        sa.Column("ev_before_inr", sa.Numeric(16, 2)),
        sa.Column("ev_after_inr", sa.Numeric(16, 2)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.execute("ALTER TABLE amendments ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE amendments FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY amendments_isolation ON amendments
        USING (org_id = {CURRENT_ORG})
        WITH CHECK (org_id = {CURRENT_ORG})
        """
    )
    op.execute("GRANT SELECT, INSERT ON amendments TO bidproof_app")


def downgrade() -> None:
    op.drop_table("amendments")
    op.drop_constraint("ck_documents_kind", "documents")
    op.drop_column("documents", "kind")
    op.drop_column("documents", "version")
    op.drop_column("decisions", "tender_value_inr")
