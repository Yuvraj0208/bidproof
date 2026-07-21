"""onboarding: org branding + onboarded flag (US-17, SPEC §15)

Revision ID: 0018
Revises: 0017
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("branding", postgresql.JSONB(), nullable=False,
                  server_default="{}"),
    )
    op.add_column(
        "organizations",
        sa.Column("onboarded_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_column("organizations", "onboarded_at")
    op.drop_column("organizations", "branding")
