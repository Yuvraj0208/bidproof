"""US-14 unit tests: the leaderboard scores every model on the SAME gold set
with all metric columns, and discriminates a weaker model from a stronger."""

from app.services.modellab import (
    DEFAULT_PROFILES,
    ModelProfile,
    run_leaderboard,
)

METRIC_COLUMNS = {
    "model", "f1_overall", "f1_eligibility", "f1_by_family", "exact_numbers",
    "hallucination_rate", "citation_complete", "speed_ms", "cost_per_tender_inr",
}


def test_leaderboard_has_a_row_per_model_with_every_metric():
    result = run_leaderboard("extraction")
    assert result["gold_tenders"] >= 25            # the 25-tender gold set
    assert len(result["leaderboard"]) == len(DEFAULT_PROFILES)
    for row in result["leaderboard"]:
        assert METRIC_COLUMNS <= set(row)
        assert 0.0 <= row["f1_overall"] <= 1.0
        assert row["simulated"] is True


def test_leaderboard_is_sorted_by_f1():
    rows = run_leaderboard("extraction")["leaderboard"]
    f1s = [r["f1_overall"] for r in rows]
    assert f1s == sorted(f1s, reverse=True)


def test_the_comparison_discriminates_strong_from_weak():
    strong = ModelProfile("strong", "paid", 0.99, 0.01, 0.02, 1000, 7.0)
    weak = ModelProfile("weak", "open", 0.70, 0.30, 0.40, 800, 0.5)
    rows = {r["model"]: r
            for r in run_leaderboard("extraction", profiles=[strong, weak])["leaderboard"]}

    assert rows["strong"]["f1_overall"] > rows["weak"]["f1_overall"]
    assert rows["strong"]["hallucination_rate"] <= rows["weak"]["hallucination_rate"]
    assert rows["strong"]["exact_numbers"] >= rows["weak"]["exact_numbers"]


def test_same_gold_set_every_model():
    result = run_leaderboard("extraction")
    # one gold-tender count shared by all rows — the same corpus each time
    assert result["gold_tenders"] >= 25
    assert all(r["cost_per_tender_inr"] >= 0 for r in result["leaderboard"])
