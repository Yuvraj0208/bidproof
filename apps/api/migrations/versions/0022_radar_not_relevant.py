"""tenders: allow radar_list = 'not_relevant'

Revision ID: 0022
Revises: 0021

Triage could only end in three places, so the last branch of the scorer swept
every confidently-scored tender that was NOT in the company's lane onto the
opportunity radar — however poor the fit. A Punjab National Bank request for
"suitable ready premises" scored 0.10 and was presented as an opportunity Godrej
could win. The radar is meant to be the tenders you *could* win but never bid on;
a list that also holds the ones you could not is noise.

`thresholds.radar` (0.45) now decides membership, and anything below it lands
here. The row is kept, not deleted: the decision is auditable and the tender is
still reachable by asking for this list by name. The default radar view hides it.
"""

from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None

_LISTS = ("in_our_lane", "opportunity_radar", "needs_human", "not_relevant")


def upgrade() -> None:
    op.drop_constraint("ck_tenders_radar_list", "tenders")
    values = ", ".join(f"'{name}'" for name in _LISTS)
    op.create_check_constraint(
        "ck_tenders_radar_list",
        "tenders",
        f"radar_list IS NULL OR radar_list IN ({values})",
    )


def downgrade() -> None:
    # Anything already scored 'not_relevant' has no home in the old three-value
    # world. Send it back to the human queue rather than dropping the row.
    op.execute(
        "UPDATE tenders SET radar_list = 'needs_human' "
        "WHERE radar_list = 'not_relevant'"
    )
    op.drop_constraint("ck_tenders_radar_list", "tenders")
    op.create_check_constraint(
        "ck_tenders_radar_list",
        "tenders",
        "radar_list IS NULL OR radar_list IN "
        "('in_our_lane', 'opportunity_radar', 'needs_human')",
    )
