"""Calibration (SPEC §12.1): from the gold-set predictions, choose the
confidence threshold for each target accuracy and report the coverage it
buys — the "auto-decide 60% of clauses at 99% accuracy, or 90% at 91%"
trade-off that sets the auto-accept band.

Honesty (SPEC §20, Constitution #8): while the gold set is synthetic or too
small, the report is marked `is_this_honest: false` — the thresholds are
placeholders until real, hand-labelled tenders replace the starter set.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from goldset_harness import GOLD_DIR, evaluate

TARGET_ACCURACIES = [0.99, 0.95, 0.90]
MIN_REAL_TENDERS_FOR_HONEST = 25
CALIBRATION_PATH = Path(__file__).resolve().parents[1] / "calibration_report.json"


@dataclass
class ThresholdChoice:
    target_accuracy: float
    threshold: float | None   # None when no threshold reaches the target
    coverage: float
    achieved_accuracy: float | None


def pick_thresholds(
    predictions: list[tuple[float, bool]],
    targets: list[float] = TARGET_ACCURACIES,
) -> list[ThresholdChoice]:
    """For each target accuracy, find the LOWEST confidence threshold whose
    accepted set meets that accuracy — that threshold maximises coverage for
    the target. Pure counting; no model."""
    total = len(predictions)
    choices: list[ThresholdChoice] = []
    candidate_thresholds = sorted({round(c, 3) for c, _ in predictions})

    for target in targets:
        best: ThresholdChoice | None = None
        for threshold in candidate_thresholds:
            accepted = [(c, ok) for c, ok in predictions if c >= threshold]
            if not accepted:
                continue
            correct = sum(1 for _, ok in accepted if ok)
            accuracy = correct / len(accepted)
            if accuracy >= target:
                coverage = len(accepted) / total if total else 0.0
                # lowest threshold that meets target = highest coverage
                if best is None or coverage > best.coverage:
                    best = ThresholdChoice(target, threshold, round(coverage, 3),
                                           round(accuracy, 3))
        choices.append(
            best or ThresholdChoice(target, None, 0.0, None)
        )
    return choices


def calibrate(gold_dir: Path = GOLD_DIR) -> dict:
    report = evaluate(gold_dir)
    predictions = list(report.predictions)
    choices = pick_thresholds(predictions)

    synthetic = _all_synthetic(gold_dir)
    tenders = report.tenders
    honest = (not synthetic) and tenders >= MIN_REAL_TENDERS_FOR_HONEST

    return {
        "tenders": tenders,
        "predictions": len(predictions),
        "all_synthetic": synthetic,
        "is_this_honest": honest,
        "note": (
            "thresholds are placeholders — the gold set is synthetic; replace "
            "with hand-labelled real tenders to calibrate for production"
            if not honest else "calibrated on the labelled gold set"
        ),
        "coverage_vs_accuracy": report.coverage_curve(),
        "auto_accept_thresholds": [
            {
                "target_accuracy": c.target_accuracy,
                "confidence_threshold": c.threshold,
                "coverage": c.coverage,
                "achieved_accuracy": c.achieved_accuracy,
            }
            for c in choices
        ],
    }


def _all_synthetic(gold_dir: Path) -> bool:
    labels = list(gold_dir.glob("*/labels.json"))
    if not labels:
        return True
    return all(
        json.loads(p.read_text(encoding="utf-8")).get("synthetic", False)
        for p in labels
    )


def write_report(gold_dir: Path = GOLD_DIR) -> dict:
    payload = calibrate(gold_dir)
    CALIBRATION_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
