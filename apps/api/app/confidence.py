"""The confidence contract (US-13): every surfaceable item exposes
{confidence, band, reason}. One threshold definition — the frontend chip
mirrors these exact numbers, and the triage scorer uses the same bands."""

GREEN_MIN = 0.7
YELLOW_MIN = 0.4


def band_for(confidence: float) -> str:
    if confidence >= GREEN_MIN:
        return "green"
    if confidence >= YELLOW_MIN:
        return "yellow"
    return "red"
