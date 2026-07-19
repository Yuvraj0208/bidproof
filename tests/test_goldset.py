"""The gold-set gate (SPEC §12.1): CI fails if eligibility-family F1 drops
below 0.85, or if a single hallucination appears. Also writes the full
report (per-family scores + coverage-vs-accuracy curve) to eval_report.json.
"""

import json
from pathlib import Path

from goldset_harness import GOLD_DIR, evaluate

REPORT_PATH = Path(__file__).resolve().parents[1] / "eval_report.json"

ELIGIBILITY_F1_FLOOR = 0.85


def test_gold_set_present():
    tenders = [p for p in GOLD_DIR.iterdir() if (p / "labels.json").exists()]
    assert len(tenders) >= 10, "the gold set must hold at least 10 labelled tenders"


def test_gold_set_gate_and_report():
    report = evaluate()
    payload = report.to_dict()
    REPORT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("\nGold-set report (per family — never blended):")
    for family, scores in payload["per_family"].items():
        print(
            f"  {family:<12} P={scores['precision']:.2f} "
            f"R={scores['recall']:.2f} F1={scores['f1']:.2f}"
        )
    print(f"  exact-number match rate: {payload['exact_number_match_rate']:.2f}")
    print(f"  hallucination rate:      {payload['hallucination_rate']:.4f}")

    assert report.tenders >= 10

    eligibility = payload["per_family"].get("eligibility")
    assert eligibility is not None, "eligibility family missing from the gold set"
    assert eligibility["f1"] >= ELIGIBILITY_F1_FLOOR, (
        f"eligibility F1 {eligibility['f1']} fell below the "
        f"{ELIGIBILITY_F1_FLOOR} floor — the build must not ship"
    )

    # Zero by structure (§9 rule 1); verified every run, not assumed.
    assert payload["hallucination_rate"] == 0.0

    curve = payload["coverage_vs_accuracy"]
    assert len(curve) >= 5
    assert all("coverage" in point and "accuracy" in point for point in curve)
