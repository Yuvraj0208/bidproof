"""The evaluation subsystem must never flatter itself.

Every test here defends one property: a number on the Evaluation screen carries
its provenance, and a component with nothing to measure says so rather than
reporting a default that reads like a score.
"""

import pytest

from app.services import evaluation
from app.services.evaluation.readers import _levenshtein, _normalise
from app.services.evaluation.types import Evaluation, GroundTruth, Metric, Status


def test_every_registered_component_is_runnable():
    for entry in evaluation.REGISTRY:
        assert entry.component in evaluation.BY_COMPONENT
        assert entry.cost in {"fast", "slow"}
        assert callable(entry.run)


def test_the_expensive_evaluators_are_opt_in():
    """OCR loads ML models and the engine comparison reads every gold PDF.
    Neither may run because someone opened a screen."""
    slow = {e.component for e in evaluation.REGISTRY if e.cost == "slow"}
    assert slow == {"ocr", "text_engines"}


def test_retrieval_reports_not_implemented_rather_than_zero():
    """There is no embedding retrieval in the product. A recall@k of 0.0 would
    read as "our retrieval is terrible" instead of "there is no retrieval"."""
    from app.services.evaluation.pipeline import evaluate_retrieval

    result = evaluate_retrieval()
    assert result.status is Status.NOT_IMPLEMENTED
    assert result.metrics == [], "a thing that does not exist has no metrics"
    assert result.ground_truth is GroundTruth.NONE
    assert "does not exist" in result.blocked_reason
    assert "tests/gold/retrieval.json" in result.how_to_fix


def test_synthetic_ground_truth_is_declared_and_caveated():
    """The gold set is generated alongside the extractor's own patterns, so it
    scores 1.00. That must never be presented as real-world accuracy."""
    from app.services.evaluation.pipeline import evaluate_rule_extraction

    result = evaluate_rule_extraction()
    if result.status is not Status.MEASURED:
        pytest.skip("gold set unavailable in this environment")
    assert result.ground_truth is GroundTruth.SYNTHETIC
    assert result.blocked_reason, "a synthetic score must carry its caveat"
    assert "synthetic" in result.blocked_reason.lower()
    assert "real tenders" in result.how_to_fix


def test_a_metric_declares_its_direction_and_sample():
    """A character error rate coloured like an accuracy is a lie told in green."""
    cer = Metric("cer", "Character error rate", 0.0088, "ratio",
                 higher_is_better=False, sample_size=341)
    payload = cer.to_dict()
    assert payload["higher_is_better"] is False
    assert payload["sample_size"] == 341


def test_levenshtein_is_correct():
    """The OCR score rests on this, so it is worth pinning."""
    assert _levenshtein("", "") == 0
    assert _levenshtein("abc", "abc") == 0
    assert _levenshtein("abc", "") == 3
    assert _levenshtein("kitten", "sitting") == 3
    assert _levenshtein("Rs 2,50,000", "Rs 2,50,00O") == 1


def test_ocr_comparison_ignores_case_and_whitespace_only():
    """Line breaks are not accuracy problems — the extractor normalises them.
    A wrong digit still must count."""
    assert _normalise("Rs  2,50,000\n shall") == _normalise("rs 2,50,000 shall")
    assert _normalise("Rs 2,50,000") != _normalise("Rs 2,50,001")


def test_error_in_an_evaluator_never_becomes_a_score():
    """An evaluation subsystem that hides its own failures is worse than none."""
    failing = Evaluation(
        component="x", label="X", what_it_measures="",
        status=Status.ERROR, ground_truth=GroundTruth.NONE,
        blocked_reason="boom",
    )
    assert failing.to_dict()["status"] == "error"
    assert failing.to_dict()["metrics"] == []
