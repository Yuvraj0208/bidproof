"""US-09 unit tests: verified / contradicted / cannot_verify, decided by
digit comparison in code."""

from bidproof_factchecker import check_text, verified_percentage

FACTS = {
    "[F:aaaaaaaa]": "Annual turnover of ₹150.00 crore in FY 2024-25",
    "[P:bbbbbbbb]": "RACK-HD-01 Heavy-duty pallet rack; lead time 45 days",
}


def test_claim_with_matching_digits_is_verified():
    claims = check_text(
        "Annual turnover of ₹150.00 crore in FY 2024-25. [F:aaaaaaaa]", FACTS
    )
    assert [c.status for c in claims] == ["verified"]
    assert claims[0].source_tag == "[F:aaaaaaaa]"


def test_claim_with_mismatched_digits_is_contradicted():
    claims = check_text(
        "Annual turnover of ₹999.00 crore in FY 2024-25. [F:aaaaaaaa]", FACTS
    )
    assert [c.status for c in claims] == ["contradicted"]


def test_factual_claim_without_tag_cannot_be_verified():
    claims = check_text("Our lead time is 45 days.", FACTS)
    assert [c.status for c in claims] == ["cannot_verify"]
    assert claims[0].source_tag is None


def test_unknown_tag_cannot_be_verified():
    claims = check_text("Lead time 45 days. [P:99999999]", FACTS)
    assert [c.status for c in claims] == ["cannot_verify"]


def test_style_sentences_are_not_claims():
    claims = check_text(
        "We thank the Authority for the opportunity. Quality is our promise.",
        FACTS,
    )
    assert claims == []


def test_tender_reference_number_is_not_a_company_claim():
    # The tender's own reference number is the buyer's words, not a claim.
    text = "We submit our proposal for Tender 42/2026."
    assert check_text(text, FACTS) != []                      # naively a claim
    assert check_text(text, FACTS, ignore_context=("Tender 42/2026",)) == []


def test_verified_percentage_and_no_claims_is_none():
    # The writer's convention: one claim per line, tag after the period.
    claims = check_text(
        "Lead time 45 days. [P:bbbbbbbb]\nTurnover ₹999 crore. [F:aaaaaaaa]",
        FACTS,
    )
    assert verified_percentage(claims) == 50.0
    assert verified_percentage([]) is None
