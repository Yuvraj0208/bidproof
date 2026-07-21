"""per-section scores for the proposal studio (US-11, SPEC §5.7)

Revision ID: 0013
Revises: 0012

Three scores per section: claims-verified % (already stored as verified_pct),
requirements-covered %, and style-match %. A section is approved individually
— there is no approve-all — and only when it has no open flags.
"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "proposal_sections",
        sa.Column("requirements_covered_pct", sa.Float()),
    )
    op.add_column(
        "proposal_sections",
        sa.Column("style_match_pct", sa.Float()),
    )
    op.add_column(
        "proposal_sections",
        sa.Column("approved_by", sa.String()),
    )
    op.add_column(
        "proposal_sections",
        sa.Column("approved_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_column("proposal_sections", "approved_at")
    op.drop_column("proposal_sections", "approved_by")
    op.drop_column("proposal_sections", "style_match_pct")
    op.drop_column("proposal_sections", "requirements_covered_pct")
