"""Calibration tests (SPEC §12.1): the threshold picker maximises coverage
for a target accuracy, and the gold-set calibration is honestly marked
synthetic until real tenders replace the starter set."""

from calibration import (
    MIN_REAL_TENDERS_FOR_HONEST,
    ThresholdChoice,
    calibrate,
    pick_thresholds,
    write_report,
)


def test_threshold_picker_trades_coverage_for_accuracy():
    # A crafted prediction set with three confidence tiers: the top tier is
    # clean, the middle tier mostly right, the bottom tier a coin toss.
    predictions = (
        [(0.95, True)] * 50            # confident + always correct
        + [(0.7, True)] * 20 + [(0.7, False)] * 5   # 80% correct
        + [(0.5, True)] * 10 + [(0.5, False)] * 10  # 50/50
    )
    choices = {c.target_accuracy: c for c in pick_thresholds(predictions, [0.99, 0.90])}

    strict = choices[0.99]
    lenient = choices[0.90]
    # a stricter accuracy target needs a higher threshold and yields less coverage
    assert strict.threshold is not None and lenient.threshold is not None
    assert strict.threshold >= lenient.threshold
    assert strict.coverage <= lenient.coverage
    assert strict.achieved_accuracy >= 0.99


def test_unreachable_target_reports_no_threshold():
    predictions = [(0.5, True), (0.5, False)]   # never better than 50%
    [choice] = pick_thresholds(predictions, [0.99])
    assert choice.threshold is None
    assert choice.coverage == 0.0


def test_gold_set_calibration_is_marked_synthetic_and_writes_report():
    report = write_report()
    assert report["tenders"] >= MIN_REAL_TENDERS_FOR_HONEST
    assert report["all_synthetic"] is True
    # honesty: not production-calibrated while the gold set is synthetic
    assert report["is_this_honest"] is False
    assert report["coverage_vs_accuracy"]
    assert len(report["auto_accept_thresholds"]) == 3
    for row in report["auto_accept_thresholds"]:
        assert "confidence_threshold" in row and "coverage" in row


def test_threshold_choice_shape():
    choice = ThresholdChoice(0.95, 0.9, 0.6, 0.97)
    assert choice.target_accuracy == 0.95 and choice.coverage == 0.6
