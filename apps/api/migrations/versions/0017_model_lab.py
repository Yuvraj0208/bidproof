"""model lab runs (US-14, SPEC §12.4)

Revision ID: 0017
Revises: 0016

Each run stores the leaderboard — the same gold set scored across N models —
so the Model Lab screen renders it and every model choice keeps its evidence.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

CURRENT_ORG = "NULLIF(current_setting('app.current_org_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "model_lab_runs",
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
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("gold_tenders", sa.Integer(), nullable=False),
        sa.Column("leaderboard", postgresql.JSONB(), nullable=False,
                  server_default="[]"),
        sa.Column("simulated", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.execute("ALTER TABLE model_lab_runs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE model_lab_runs FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY model_lab_runs_isolation ON model_lab_runs
        USING (org_id = {CURRENT_ORG})
        WITH CHECK (org_id = {CURRENT_ORG})
        """
    )
    op.execute("GRANT SELECT, INSERT ON model_lab_runs TO bidproof_app")


def downgrade() -> None:
    op.drop_table("model_lab_runs")
