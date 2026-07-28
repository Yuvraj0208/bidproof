"""verdicts: let a human settle the ones the system refused to guess

Revision ID: 0021
Revises: 0020

The matrix has always been able to say `needs_human` — "no arithmetic and no
cited judgement could settle this, so it is yours" — and the Review Hub counted
those as blocking submission. But there was nowhere to actually give the answer.
The product asked a question it gave no way to answer.

Four columns, so a human decision is never mistaken for a machine one:

* `system_verdict` keeps what the checker said before anyone intervened, so the
  override is always visible and reversible. NULL means untouched.
* `decided_by` / `decided_at` / `decided_reason` record who settled it and why.
  A verdict a human asserted with no reason is not evidence, so the reason is
  required by the API.

The verdict column itself still holds the *effective* answer, which is what the
compliance matrix, the export blocker and the EV calculation must read.
"""

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("verdicts", sa.Column("system_verdict", sa.String(), nullable=True))
    op.add_column("verdicts", sa.Column("decided_by", sa.String(), nullable=True))
    op.add_column(
        "verdicts",
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("verdicts", sa.Column("decided_reason", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("verdicts", "decided_reason")
    op.drop_column("verdicts", "decided_at")
    op.drop_column("verdicts", "decided_by")
    op.drop_column("verdicts", "system_verdict")
