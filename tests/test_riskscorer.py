"""RiskScorer unit tests: each flag fires on its condition with rupee
impacts computed by plain arithmetic; unknown inputs emit nothing."""

from datetime import datetime, timedelta, timezone

from bidproof_riskscorer import RiskInputs, RiskThresholds, score_risks

NOW = datetime(2026, 7, 20, tzinfo=timezone.utc)


def inputs(**kw):
    defaults = dict(tender_value_inr=None, closing_at=None, now=NOW,
                    best_lead_time_days=None)
    defaults.update(kw)
    return RiskInputs(**defaults)


def by_code(flags):
    return {f.code: f for f in flags}


def test_pbg_flag_with_rupee_impact():
    flags = by_code(score_risks(inputs(
        pbg_percent=10.0, pbg_el_id="el-1", tender_value_inr=5e7)))
    flag = flags["pbg_too_high"]
    assert flag.severity == "high"          # 10% >= 2x the 5% policy
    assert flag.rupee_impact == 5e6         # 10% of ₹5 cr, by code
    assert flag.el_id == "el-1"


def test_pbg_at_policy_does_not_flag():
    assert score_risks(inputs(pbg_percent=5.0, tender_value_inr=5e7)) == []


def test_oversized_emd_flag():
    flags = by_code(score_risks(inputs(
        emd_amount_inr=2.5e6, tender_value_inr=5e7)))  # 5% of value, cap 2%
    flag = flags["oversized_emd"]
    assert flag.rupee_impact == 2.5e6
    assert "5.0%" in flag.message


def test_emd_without_tender_value_emits_nothing():
    assert score_risks(inputs(emd_amount_inr=2.5e6)) == []


def test_delivery_infeasible_flag():
    flags = by_code(score_risks(inputs(delivery_days=30, best_lead_time_days=45,
                                       delivery_el_id="el-9")))
    assert flags["delivery_infeasible"].severity == "high"
    assert flags["delivery_infeasible"].el_id == "el-9"


def test_query_deadline_passed_flag():
    closing = NOW + timedelta(days=5)
    flags = by_code(score_risks(inputs(closing_at=closing, query_window_days=14)))
    assert "query_deadline_passed" in flags

    still_open = NOW + timedelta(days=30)
    assert score_risks(inputs(closing_at=still_open, query_window_days=14)) == []


def test_thresholds_are_config_not_code():
    lenient = RiskThresholds(pbg_max_percent=15.0)
    assert score_risks(inputs(pbg_percent=10.0, tender_value_inr=5e7), lenient) == []
