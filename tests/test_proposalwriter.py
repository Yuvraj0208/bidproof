"""US-09 unit tests: the fact context, enforced source tags, and the
deterministic grounded writer."""

import uuid

from bidproof_proposalwriter import (
    DEFAULT_SECTIONS,
    build_fact_context,
    deterministic_section,
    enforce_source_tags,
    is_factual,
)

FACT_ID = uuid.uuid4()
PRODUCT_ID = uuid.uuid4()

FACTS = [{
    "id": FACT_ID, "fact_type": "turnover", "value_number": 1.5e9,
    "fiscal_year": "2024-25", "legal_entity": "Demo Manufacturing Co Ltd",
}]
PRODUCTS = [{
    "id": PRODUCT_ID, "product_code": "RACK-HD-01",
    "product_name": "Heavy-duty pallet rack",
    "standards": ["IS 4923", "ISO 9001"], "lead_time_days": 45,
    "capacity_per_month": 500,
}]


def test_fact_context_renders_tagged_lines():
    tagged = build_fact_context(FACTS, PRODUCTS)
    assert len(tagged) == 2
    fact = tagged[0]
    assert fact.tag == f"[F:{FACT_ID.hex[:8]}]"
    assert "₹150.00 crore" in fact.text and "2024-25" in fact.text
    product = tagged[1]
    assert product.tag == f"[P:{PRODUCT_ID.hex[:8]}]"
    assert "IS 4923" in product.text and "45 days" in product.text


def test_deterministic_writer_tags_every_factual_sentence():
    tagged = build_fact_context(FACTS, PRODUCTS)
    valid = {t.tag for t in tagged}
    for section in DEFAULT_SECTIONS:
        text = deterministic_section(section, "Tender 42/2026", "Demo Co",
                                     tagged, [])
        # The tender's own title is quoted context, not a company claim.
        kept, dropped = enforce_source_tags(
            text, valid, allowed_context=("Tender 42/2026",)
        )
        assert dropped == 0, f"section {section} emitted an ungrounded fact"
        assert kept.strip(), f"section {section} is empty"


def test_enforce_drops_untagged_factual_sentence_and_counts_it():
    valid = {"[F:aaaaaaaa]"}
    text = ("Our turnover is ₹500 crore.\n"            # factual, no tag → drop
            "We are committed to quality.\n"            # style → keep
            "Certified since 2019. [F:aaaaaaaa]")       # tagged → keep
    kept, dropped = enforce_source_tags(text, valid)
    assert dropped == 1
    assert "₹500 crore" not in kept
    assert "committed to quality" in kept
    assert "[F:aaaaaaaa]" in kept


def test_enforce_drops_unknown_tag():
    kept, dropped = enforce_source_tags(
        "Turnover ₹9 crore. [F:deadbeef]", valid_tags=set()
    )
    assert dropped == 1 and kept == ""


def test_style_sentences_pass_untagged():
    kept, dropped = enforce_source_tags(
        "We appreciate the opportunity to bid.", valid_tags=set()
    )
    assert dropped == 0 and "opportunity" in kept


def test_is_factual_ignores_tag_hex_digits():
    assert is_factual("Lead time 45 days. [P:1a2b3c4d]")
    assert not is_factual("Quality is our promise. [F:1a2b3c4d]".replace("[F:1a2b3c4d]", ""))
    assert not is_factual("Quality is our promise. [F:1a2b3c4d]")


def test_tender_dictated_sections_override_default():
    tagged = build_fact_context(FACTS, [])
    custom = ["company_profile", "declarations"]  # the tender's format wins
    outputs = [deterministic_section(s, "T", "Co", tagged, []) for s in custom]
    assert len(outputs) == 2
    assert "declare" in outputs[1].lower()
