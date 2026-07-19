"""Matcher unit tests: arithmetic verdicts (no model can even be passed in),
and the cited judge's void rule."""

import uuid
from datetime import date

from bidproof_matcher import (
    ARITHMETIC_KEYS,
    CheckRule,
    FactRef,
    KeywordRetriever,
    ProductRef,
    Verdict,
    check_rule,
    parse_inr,
)
from bidproof_matcher.judge import (
    JudgeCall,
    parse_judge_response,
    validate_judge_citations,
)

TODAY = date(2026, 7, 20)


def rule(key, value, family="eligibility"):
    return CheckRule(
        rule_id=str(uuid.uuid4()), family=family, key=key,
        requirement_text=f"requirement for {key}", value_text=value,
        el_id=str(uuid.uuid4()),
    )


def fact(fact_type, **kw):
    return FactRef(id=str(uuid.uuid4()), fact_type=fact_type, **kw)


def product(**kw):
    defaults = dict(id=str(uuid.uuid4()), product_code="P-1", product_name="Rack")
    defaults.update(kw)
    return ProductRef(**defaults)


TURNOVER_FACTS = [
    fact("turnover", value_number=1.2e9, fiscal_year="2022-23"),
    fact("turnover", value_number=1.35e9, fiscal_year="2023-24"),
    fact("turnover", value_number=1.5e9, fiscal_year="2024-25"),
]


# --- Arithmetic: numbers by code, never a model -----------------------------


def test_turnover_average_complies_with_exact_math():
    result = check_rule(rule("min_turnover", "Rs 5 crore"), TURNOVER_FACTS, [], TODAY)
    assert result.verdict is Verdict.COMPLIES
    assert result.arithmetic is True
    assert "₹135.00 cr" in result.reason  # (120+135+150)/3, computed by code
    assert result.cited_fact_id is not None


def test_turnover_gap_when_average_below_requirement():
    result = check_rule(rule("min_turnover", "Rs 200 crore"), TURNOVER_FACTS, [], TODAY)
    assert result.verdict is Verdict.GAP


def test_turnover_without_facts_abstains():
    result = check_rule(rule("min_turnover", "Rs 5 crore"), [], [], TODAY)
    assert result.verdict is Verdict.NEEDS_HUMAN
    assert "no verified turnover facts" in result.reason


def test_delivery_verdicts_both_ways():
    products = [product(lead_time_days=45), product(product_code="P-2", lead_time_days=75)]
    ok = check_rule(rule("delivery_days", "90", "commercial"), [], products, TODAY)
    assert ok.verdict is Verdict.COMPLIES and ok.cited_product_id is not None

    tight = check_rule(rule("delivery_days", "30", "commercial"), [], products, TODAY)
    assert tight.verdict is Verdict.GAP


def test_standard_valid_expired_and_missing():
    certs = [fact("certification", value_text="ISO 9001:2015",
                  valid_until=date(2027, 8, 31))]
    ok = check_rule(rule("required_standard", "ISO 9001", "technical"), certs, [], TODAY)
    assert ok.verdict is Verdict.COMPLIES

    expired = [fact("certification", value_text="ISO 9001:2015",
                    valid_until=date(2025, 1, 1))]
    partial = check_rule(rule("required_standard", "ISO 9001", "technical"),
                         expired, [], TODAY)
    assert partial.verdict is Verdict.PARTIAL
    assert "expired" in partial.reason

    gap = check_rule(rule("required_standard", "ISO 27001", "technical"),
                     certs, [], TODAY)
    assert gap.verdict is Verdict.GAP


def test_commercial_terms_are_not_applicable():
    for key in ("emd_amount", "pbg_percent", "prebid_query_window_days"):
        result = check_rule(rule(key, "5", "commercial"), [], [], TODAY)
        assert result.verdict is Verdict.NOT_APPLICABLE
        assert result.arithmetic is True


def test_arithmetic_checkers_cannot_touch_a_model():
    """Structural guarantee (§9 rule 2): no checker signature accepts any
    model, gateway, or client — an LLM call is impossible, not just avoided."""
    import inspect

    for checker in ARITHMETIC_KEYS.values():
        params = set(inspect.signature(checker).parameters)
        assert not params & {"gateway", "model", "client", "llm"}


def test_parse_inr():
    assert parse_inr("Rs 2,50,000") == 250000
    assert parse_inr("₹5 crore") == 5e7
    assert parse_inr("12 lakh") == 12e5
    assert parse_inr("no amount") is None
    assert parse_inr(None) is None


# --- The judge: both citations or void --------------------------------------


CANDIDATES = [product(id="prod-1"), product(id="prod-2", product_code="P-2")]
SPEC_RULE = CheckRule(rule_id="r-1", family="technical", key="powder_coating",
                      requirement_text="racks shall be powder coated 80 microns",
                      value_text=None, el_id="el-99")


def test_judge_with_both_citations_is_valid():
    call = JudgeCall(verdict="complies", tender_el_id="el-99",
                     product_id="prod-1", reason="spec covered")
    assert validate_judge_citations(call, SPEC_RULE, CANDIDATES) is True


def test_judge_missing_either_citation_is_void():
    wrong_el = JudgeCall(verdict="complies", tender_el_id="el-FABRICATED",
                         product_id="prod-1", reason="x")
    assert validate_judge_citations(wrong_el, SPEC_RULE, CANDIDATES) is False

    wrong_product = JudgeCall(verdict="complies", tender_el_id="el-99",
                              product_id="prod-INVENTED", reason="x")
    assert validate_judge_citations(wrong_product, SPEC_RULE, CANDIDATES) is False


def test_judge_schema_strictness():
    assert parse_judge_response("not json") is None
    assert parse_judge_response('{"verdict": "sounds_good", "tender_el_id": "e",'
                                ' "product_id": "p", "reason": "r"}') is None
    ok = parse_judge_response('{"verdict": "partial", "tender_el_id": "el-99",'
                              ' "product_id": "prod-1", "reason": "close match"}')
    assert ok is not None and ok.verdict == "partial"


def test_keyword_retriever_finds_relevant_products():
    products = [
        product(id="a", product_name="Heavy-duty pallet rack",
                standards=("IS 4923",)),
        product(id="b", product_code="CCTV-1", product_name="CCTV camera"),
    ]
    hits = KeywordRetriever().retrieve("supply of pallet racks per IS 4923", products)
    assert [p.id for p in hits] == ["a"]
