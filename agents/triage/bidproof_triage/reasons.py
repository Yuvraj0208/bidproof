"""The one triage reason that perishes.

Every other reason on a radar card is a fact about the tender or the org —
which category matched, whether the value sits in the band, whether we have won
here before. Those stay true however long the card sits on the radar. "closes in
N days" is different: it is a fact about *today*, and it rots at exactly one day
per day.

That is not academic. A CWC tender triaged on 30 July 2026 was still explaining
itself with "closes in 8 days" on 3 August, next to a countdown chip reading
"4d left" — one card, two answers, on the number a bidder can least afford to
misread. Discovery could not correct it either: re-listing a tender already in
the database is a duplicate and returns early, so nothing ever rewrote the
sentence.

SPEC section 3.2 frames the reason list as the card explaining itself — present
tense — so the deadline phrase is composed when the card is *read*, from the
stored `closing_at`, while the durable reasons stay exactly as the original
triage recorded them.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from bidproof_triage.signals import days_to_close

# The complete vocabulary. It lives here, beside the predicate that recognises
# it, so the writer and the reader of these strings cannot drift apart.
UNKNOWN = "closing date unknown"
PASSED = "closing date has passed"
COUNTDOWN_PREFIX = "closes in "


def deadline_reason(closing_at: datetime | None, now: datetime) -> str:
    """How the card should describe its deadline, as of `now`."""
    days = days_to_close(closing_at, now)
    if days is None:
        return UNKNOWN
    if days < 0:
        return PASSED
    return f"{COUNTDOWN_PREFIX}{days} days"


def is_deadline_reason(reason: str) -> bool:
    """Whether a stored reason is the perishable one."""
    return reason in (UNKNOWN, PASSED) or reason.startswith(COUNTDOWN_PREFIX)


def refresh_deadline_reason(
    reasons: Sequence[str], closing_at: datetime | None, now: datetime
) -> list[str]:
    """The stored reasons with the deadline phrase recomputed for `now`.

    Replaced where it stood, so a card does not reshuffle its explanation as the
    days pass. Appended if the stored triage predates this function — and an
    empty list is left empty, because a card whose only line is a countdown has
    not explained itself at all.
    """
    if not reasons:
        return []

    fresh = deadline_reason(closing_at, now)
    refreshed = list(reasons)
    for index, reason in enumerate(refreshed):
        if is_deadline_reason(reason):
            refreshed[index] = fresh
            return refreshed
    refreshed.append(fresh)
    return refreshed
