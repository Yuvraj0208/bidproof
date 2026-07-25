"""rules: clause reference + obligation type (FINISH_STATUS D7)

Revision ID: 0020
Revises: 0019

A rule was stored with only its key, a value and the whole page it was found
on. A bid manager needs the tender's OWN reference for the clause ("Clause
4.2") and whether it actually binds — a mandatory clause missed is a
disqualification, an optional one is a preference.

`obligation` defaults to 'mandatory': for a tender that is the safe reading,
since treating a binding clause as optional could lose the bid.
"""

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rules", sa.Column("clause_ref", sa.String(), nullable=True))
    op.add_column(
        "rules",
        sa.Column(
            "obligation",
            sa.String(),
            nullable=False,
            server_default="mandatory",
        ),
    )
    op.create_check_constraint(
        "ck_rules_obligation",
        "rules",
        "obligation IN ('mandatory','recommended','optional')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_rules_obligation", "rules", type_="check")
    op.drop_column("rules", "obligation")
    op.drop_column("rules", "clause_ref")
