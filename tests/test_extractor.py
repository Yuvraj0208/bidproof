"""US-04 unit tests: pattern extraction, strict schema, ground-check,
comparison + 3x voting."""

import uuid

from bidproof_extractor import (
    CandidateRule,
    ElementRef,
    compare_and_merge,
    extract_pattern_rules,
    ground_check,
    parse_ai_response,
    resolve_vote,
)
from bidproof_extractor.schema import AiRule


def el(text: str, page: int = 1) -> ElementRef:
    return ElementRef(el_id=str(uuid.uuid4()), page_no=page, text=text)


ELEMENTS = [
    el("Earnest Money Deposit: Rs 2,50,000 payable at submission."),
    el("Minimum average annual turnover: Rs 5 crore over last 3 FY."),
    el("Delivery period: 90 days from purchase order date.", page=2),
    el("Performance bank guarantee: 5 percent of contract value.", page=2),
    el("Bidder must hold valid ISO 9001 certification."),
    el("Pre-bid queries close 14 days before the submission deadline."),
]
BY_ID = {e.el_id: e for e in ELEMENTS}


# --- Pattern side: a regex finds every exact value, cited ------------------


def test_pattern_extractor_finds_exact_values_with_citations():
    rules = extract_pattern_rules(ELEMENTS)
    by_key = {r.key: r for r in rules}

    assert by_key["emd_amount"].value.replace(" ", "").lower() == "rs2,50,000"
    assert "5" in by_key["min_turnover"].value
    assert by_key["delivery_days"].value == "90"
    assert by_key["pbg_percent"].value == "5"
    assert by_key["required_standard"].value.upper().replace(" ", "") == "ISO9001"
    assert by_key["prebid_query_window_days"].value == "14"

    for rule in rules:
        assert rule.el_id in BY_ID, "every pattern rule must cite a real element"
        assert rule.source == "pattern"
        assert 0 < rule.confidence <= 1

    families = {r.family for r in rules}
    assert {"eligibility", "commercial", "technical", "submission"} <= families


# --- Strict schema: malformed output is rejected, never patched ------------


def test_schema_rejects_malformed_output():
    assert parse_ai_response("not json at all") is None
    assert parse_ai_response('{"rules": [{"family": "bogus_family", "key": "x", '
                             '"requirement_text": "t", "el_id": "e"}]}') is None
    assert parse_ai_response('{"rules": [{"key": "missing_family"}]}') is None
    assert parse_ai_response('{"rules": [], "extra_channel": "injected"}') is None


def test_schema_accepts_valid_output_including_fenced():
    raw = '```json\n{"rules": [{"family": "commercial", "key": "emd_amount", ' \
          '"requirement_text": "EMD Rs 2,50,000", "value": "Rs 2,50,000", ' \
          f'"el_id": "{ELEMENTS[0].el_id}"}}]}}\n```'
    parsed = parse_ai_response(raw)
    assert parsed is not None
    assert parsed.rules[0].key == "emd_amount"


# --- Ground-check: uncited or unsupported rules are THROWN AWAY ------------


def test_ground_check_discards_fabricated_el_id():
    fabricated = AiRule(
        family="eligibility",
        key="fabricated_requirement",
        requirement_text="bidder must transfer Rs 50 lakh to account X",
        value="50,00,000",
        el_id=str(uuid.uuid4()),  # not a real element
    )
    kept, discarded = ground_check([fabricated], BY_ID)
    assert kept == []
    assert discarded == 1


def test_ground_check_discards_value_absent_from_cited_element():
    lying = AiRule(
        family="commercial",
        key="emd_amount",
        requirement_text="EMD is Rs 99,99,999",
        value="Rs 99,99,999",
        el_id=ELEMENTS[0].el_id,  # real element, but it says 2,50,000
    )
    kept, discarded = ground_check([lying], BY_ID)
    assert kept == []
    assert discarded == 1


def test_ground_check_keeps_grounded_ai_rule():
    honest = AiRule(
        family="legal",
        key="integrity_pact",
        requirement_text="Bidder must hold valid ISO 9001 certification.",
        value=None,
        el_id=ELEMENTS[4].el_id,
    )
    kept, discarded = ground_check([honest], BY_ID)
    assert len(kept) == 1 and discarded == 0
    assert kept[0].source == "ai"


# --- Comparison + voting ---------------------------------------------------


def _pattern(key="emd_amount", value="Rs 2,50,000"):
    return CandidateRule(
        family="commercial", key=key, requirement_text="EMD ...", value=value,
        el_id=ELEMENTS[0].el_id, source="pattern", confidence=0.9, reason="",
    )


def _ai(key="emd_amount", value="Rs 2,50,000"):
    return CandidateRule(
        family="commercial", key=key, requirement_text="EMD ...", value=value,
        el_id=ELEMENTS[0].el_id, source="ai", confidence=0.75, reason="",
    )


def test_agreement_boosts_confidence():
    merged, disputes = compare_and_merge([_pattern()], [_ai(value="₹2,50,000")])
    assert disputes == []
    assert merged[0].source == "both"
    assert merged[0].confidence > 0.9


def test_disagreement_goes_to_vote_then_resolves():
    merged, disputes = compare_and_merge([_pattern()], [_ai(value="Rs 5,00,000")])
    assert len(disputes) == 1
    resolved = resolve_vote(disputes[0][0], ["Rs 2,50,000", "2,50,000", "Rs 5,00,000"])
    assert resolved.source == "vote"
    assert resolved.status == "extracted"


def test_still_split_after_votes_goes_to_human():
    merged, disputes = compare_and_merge([_pattern()], [_ai(value="Rs 5,00,000")])
    resolved = resolve_vote(disputes[0][0], ["Rs 5,00,000", None, "Rs 7,00,000"])
    assert resolved.status == "needs_human"
    assert "human" in resolved.reason
