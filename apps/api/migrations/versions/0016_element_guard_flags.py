"""guard flags on parsed elements (US-19, SPEC §10, §11.1)

Revision ID: 0016
Revises: 0015

The injection scanner runs over every parsed element. Suspicious text is
FLAGGED for the human reviewer — and treated as inert data. Marking the
element (not deleting it) keeps the proof chain intact while making the
attack visible; the ground-check + schemas + least privilege stop it doing
anything.
"""

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "elements",
        sa.Column("guard_flagged", sa.Boolean(), nullable=False,
                  server_default="false"),
    )
    op.add_column("elements", sa.Column("guard_category", sa.String()))


def downgrade() -> None:
    op.drop_column("elements", "guard_category")
    op.drop_column("elements", "guard_flagged")
