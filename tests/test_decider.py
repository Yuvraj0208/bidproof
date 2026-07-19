"""US-06 unit tests: EV computed exactly from fixtures by plain code, the
hard gate, and honest abstention when the value is unknown."""

from bidproof_decider import EvConfig, decide, hard_gate

CFG = EvConfig(p_win=0.3, profit_margin_percent=10.0, man_days=12,
               loaded_day_rate_inr=15000, capital_rate_annual=0.12,
               lock_months=6)

CLEAN_VERDICTS = [
    {"family": "eligibility", "key": "min_turnover", "verdict": "complies"},
    {"family": "commercial", "key": "emd_amount", "verdict": "not_applicable"},
]


def test_ev_computed_exactly_term_by_term():
    # value ₹5 cr, EMD ₹2.5 lakh, PBG 5%:
    #   expected profit = 0.3 × 10% × 5,00,00,000            = 15,00,000
    #   bid effort      = 12 × 15,000                        = -1,80,000
    #   locked money    = (2,50,000 + 25,00,000) × 12% × 6/12 = -1,65,000
    #   EV                                                    = 11,55,000
    outcome = decide(CLEAN_VERDICTS, tender_value_inr=5e7, emd_inr=250000,
                     pbg_percent=5.0, config=CFG)
    assert outcome.recommendation == "go"
    assert outcome.ev_inr == 1_155_000.0

    by_key = {t["key"]: t for t in outcome.terms}
    assert by_key["expected_profit"]["value_inr"] == 1_500_000.0
    assert by_key["bid_effort"]["value_inr"] == -180_000.0
    assert by_key["locked_capital"]["value_inr"] == -165_000.0
    assert "12 man-days × ₹15,000/day" in by_key["bid_effort"]["formula"]


def test_negative_ev_is_no_go():
    outcome = decide(CLEAN_VERDICTS, tender_value_inr=5e6, emd_inr=250000,
                     pbg_percent=5.0, config=CFG)
    # expected profit 1.5L < effort 1.8L + locked costs → negative
    assert outcome.ev_inr < 0
    assert outcome.recommendation == "no_go"


def test_hard_gate_overrides_any_ev():
    failed = CLEAN_VERDICTS + [
        {"family": "eligibility", "key": "required_licence", "verdict": "gap"}
    ]
    outcome = decide(failed, tender_value_inr=5e9, emd_inr=0, pbg_percent=0,
                     config=CFG)
    assert outcome.recommendation == "no_go"
    assert outcome.ev_inr is None  # EV not even computed — the gate decides
    assert outcome.gate_failed[0]["key"] == "required_licence"
    assert "override" in outcome.reason  # human path advertised


def test_hard_gate_only_counts_eligibility_gaps():
    verdicts = [
        {"family": "commercial", "key": "delivery_days", "verdict": "gap"},
        {"family": "eligibility", "key": "min_turnover", "verdict": "needs_human"},
    ]
    assert hard_gate(verdicts) == []


def test_unknown_value_abstains_never_guesses():
    outcome = decide(CLEAN_VERDICTS, tender_value_inr=None, emd_inr=None,
                     pbg_percent=None, config=CFG)
    assert outcome.recommendation == "needs_human"
    assert outcome.ev_inr is None
    assert "unknown" in outcome.reason


def test_ev_config_is_config_not_code():
    optimistic = EvConfig(p_win=0.9, profit_margin_percent=10.0, man_days=12,
                          loaded_day_rate_inr=15000, capital_rate_annual=0.12,
                          lock_months=6)
    a = decide(CLEAN_VERDICTS, 5e7, 250000, 5.0, CFG).ev_inr
    b = decide(CLEAN_VERDICTS, 5e7, 250000, 5.0, optimistic).ev_inr
    assert b > a
