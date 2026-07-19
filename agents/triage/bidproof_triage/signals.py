"""Deterministic signal extraction. A regex finds every number an AI would
otherwise be tempted to guess (§9 rule 2); no match means None, never an
invented value."""

import re
from datetime import datetime

_AMOUNT_RE = re.compile(
    r"(?:₹|\brs\.?|\binr)\s*([\d,]+(?:\.\d+)?)\s*(crore|cr|lakh|lacs?)?",
    re.IGNORECASE,
)

_MULTIPLIERS = {
    None: 1.0,
    "cr": 1e7,
    "crore": 1e7,
    "lakh": 1e5,
    "lac": 1e5,
    "lacs": 1e5,
}


def extract_value_inr(text: str) -> float | None:
    """Largest rupee amount present in the text (contract values dwarf EMDs
    and fees, so max is the tender value by construction). None if nothing
    parseable is present."""
    best: float | None = None
    for match in _AMOUNT_RE.finditer(text):
        digits = match.group(1).replace(",", "")
        try:
            amount = float(digits)
        except ValueError:
            continue
        unit = (match.group(2) or "").lower() or None
        amount *= _MULTIPLIERS.get(unit, 1.0)
        if best is None or amount > best:
            best = amount
    return best


def days_to_close(closing_at: datetime | None, now: datetime) -> int | None:
    if closing_at is None:
        return None
    return (closing_at - now).days
