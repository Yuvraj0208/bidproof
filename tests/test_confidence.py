"""US-13: the confidence contract. One band definition — these exact
thresholds are mirrored by the frontend chip (apps/web/src/confidence.ts)."""

from app.confidence import band_for


def test_confidence_band_thresholds():
    assert band_for(1.0) == "green"
    assert band_for(0.7) == "green"
    assert band_for(0.69) == "yellow"
    assert band_for(0.4) == "yellow"
    assert band_for(0.39) == "red"
    assert band_for(0.0) == "red"
