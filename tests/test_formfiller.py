"""FormFiller unit tests (SPEC §5.8): real data fills a field; missing data
is left blank and flagged; a legal declaration is never guessed."""

from bidproof_formfiller import (
    STANDARD_DECLARATIONS,
    fill_declaration,
    template_by_id,
)

FULL_CONTEXT = {
    "company_legal_name": "Demo Manufacturing Co Ltd",
    "latest_turnover": "₹150.00 crore (FY 2024-25)",
    "net_worth": "₹210.00 crore",
    "msme_status": "not_msme",
    "blacklist_status": "Not blacklisted by any government agency",
    "authorised_signatory": None,   # a human's to sign
    "signatory_designation": None,
    "registered_office": None,
    "place": None,
    "declaration_date": None,
}


def test_known_field_is_filled_from_real_data():
    template = template_by_id("non_blacklisting")
    result = fill_declaration(template, FULL_CONTEXT)
    by_key = {f.key: f for f in result.fields}
    assert by_key["company_name"].filled is True
    assert by_key["company_name"].value == "Demo Manufacturing Co Ltd"
    assert by_key["company_name"].flagged is False
    assert by_key["blacklist_status"].value.startswith("Not blacklisted")


def test_unknown_field_left_blank_and_flagged():
    template = template_by_id("non_blacklisting")
    result = fill_declaration(template, FULL_CONTEXT)
    signatory = next(f for f in result.fields if f.key == "authorised_signatory")
    assert signatory.value is None
    assert signatory.filled is False
    assert signatory.flagged is True
    assert signatory.reason                      # tells the human why
    assert not result.complete                   # a flagged field blocks completion


def test_missing_capability_data_is_flagged_not_invented():
    # Empty context — nothing is known. The FormFiller must guess nothing.
    empty: dict[str, str | None] = {}
    for template in STANDARD_DECLARATIONS:
        result = fill_declaration(template, empty)
        assert all(f.value is None for f in result.fields)
        assert all(f.flagged for f in result.fields)
        assert result.flagged_count == len(result.fields)


def test_blank_string_is_treated_as_missing():
    template = template_by_id("financial_capability")
    context = dict(FULL_CONTEXT, latest_turnover="   ")
    result = fill_declaration(template, context)
    turnover = next(f for f in result.fields if f.key == "latest_turnover")
    assert turnover.flagged is True and turnover.value is None


def test_every_filled_field_records_its_source():
    template = template_by_id("financial_capability")
    result = fill_declaration(template, FULL_CONTEXT)
    for field in result.fields:
        if field.filled:
            assert field.source                  # provenance on every value
