"""Missing data is declared, never invented (docs/REFERENCE_PROPOSAL.md, rule 2).

The reference proposal calls this the single most important behaviour in the
document, and the example it gives is exact: the capability database holds no
lead time for any of the twelve product lines, so the bid cannot confirm the
60-day completion period. It writes

    [TO BE CONFIRMED: manufacturing lead time — not in capability DB]

and raises a pre-bid query, rather than writing "delivery within 60 days is
confirmed" and fabricating the most consequential commitment in the bid.

Before this, the writer's behaviour on a missing field was to SKIP it. That is
not safe, it is only quiet: the gap leaves no trace in the document, nobody is
prompted to fill it, and a reader assumes the silence means agreement.
"""

from bidproof_proposalwriter.writer import (
    UNKNOWN_RE,
    build_fact_context,
    enforce_source_tags,
    unknown,
)


def product(**overrides) -> dict:
    base = {
        "id": type("U", (), {"hex": "abcdef1234567890"})(),
        "product_code": "SPR-1000",
        "product_name": "Selective Pallet Racking",
        "standards": ["EN 15512", "FEM"],
        "lead_time_days": None,
        "capacity_per_month": None,
    }
    base.update(overrides)
    return base


def test_a_missing_lead_time_is_written_into_the_document():
    """The gap has to appear in the prose. Skipping it is how a bid ends up
    silently agreeing to a delivery date nobody has checked."""
    context = build_fact_context([], [product()])
    text = " ".join(f.text for f in context)

    assert "lead time" in text
    assert UNKNOWN_RE.search(text), "the missing lead time left no trace"


def test_a_missing_capacity_is_declared_too():
    context = build_fact_context([], [product()])
    text = " ".join(f.text for f in context)
    assert "[TO BE CONFIRMED: monthly capacity" in text


def test_a_known_value_is_stated_plainly_not_flagged():
    """The placeholder is for absence only — a real figure must read as one."""
    context = build_fact_context(
        [], [product(lead_time_days=45, capacity_per_month=900)]
    )
    text = " ".join(f.text for f in context)

    assert "lead time 45 days" in text
    assert "capacity 900 units/month" in text
    assert "[TO BE CONFIRMED: lead time" not in text
    assert "[TO BE CONFIRMED: monthly capacity" not in text


def test_the_declared_gap_survives_the_ground_check():
    """The regression this file exists for.

    `enforce_source_tags` drops any factual sentence without a source tag. A
    declared gap has no tag by definition — there is nothing to cite — so
    without an explicit carve-out the ground-check would delete the one
    sentence in the bid that admits the product does not know something.
    """
    line = (
        "The manufacturing lead time is "
        + unknown("lead time")
        + " and will be confirmed before award."
    )
    kept, dropped = enforce_source_tags(line, valid_tags=set())

    assert dropped == 0
    assert "[TO BE CONFIRMED: lead time" in kept


def test_an_untagged_invented_number_is_still_dropped():
    """The carve-out must not become a hole. A sentence stating a figure with
    no tag and no declared gap is exactly what the ground-check is for."""
    kept, dropped = enforce_source_tags(
        "The manufacturing lead time is 45 days.", valid_tags=set()
    )
    assert dropped == 1
    assert "45 days" not in kept


def test_the_placeholder_names_the_field_and_says_why():
    """A reader has to know what to go and find. "Unknown" is not actionable;
    "lead time — not in capability DB" tells them which record to fill."""
    text = unknown("net worth as on 31.03.2025")
    assert "net worth as on 31.03.2025" in text
    assert "not in capability DB" in text

    custom = unknown("blacklisting status", "recorded without a verifiable source")
    assert "recorded without a verifiable source" in custom


def test_every_section_still_carries_facts_after_a_tag_format_change():
    """The regression that shipped in c465448.

    `_facts_of` filtered by tag PREFIX. When tags moved from [F:hash] to
    [SRC: path] every call site still asked for "[F:" and matched nothing, so
    each deterministic section kept its opening sentence and lost every fact
    beneath it. The suite stayed green: no test asserted that a section
    contains more than boilerplate.

    A section with a lead line and no evidence is exactly the three-paragraph
    output docs/REFERENCE_PROPOSAL.md calls a failure.
    """
    from bidproof_proposalwriter.writer import build_fact_context, deterministic_section

    facts = [{
        "id": type("U", (), {"hex": "aaaaaaaa1111"})(),
        "fact_type": "turnover", "value_number": 1.5e9,
        "fiscal_year": "2024-25", "value_text": None,
        "legal_entity": None, "valid_until": None,
    }]
    tagged = build_fact_context(facts, [product(lead_time_days=45)])

    for section in ("company_profile", "eligibility_compliance", "technical_approach"):
        body = deterministic_section(section, "A Tender", "Godrej", tagged, [])
        lines = [ln for ln in body.splitlines() if ln.strip()]
        assert len(lines) > 1, (
            f"{section} produced only its opening line — the facts beneath it "
            "were filtered out by a tag prefix that no longer matches"
        )
