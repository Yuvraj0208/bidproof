"""US-02 unit tests: the deterministic fit score, list assignment, config
weights, abstention, and value extraction."""

from datetime import datetime, timedelta, timezone

from bidproof_triage import (
    Category,
    OrgProfile,
    TenderSignals,
    Thresholds,
    deadline_reason,
    extract_value_inr,
    refresh_deadline_reason,
    triage,
)

NOW = datetime(2026, 7, 18, tzinfo=timezone.utc)

PROFILE = OrgProfile(
    categories=(Category("storage racks", ("storage", "rack", "warehouse")),),
    value_band_inr=(1e7, 1e9),  # ₹1 cr – ₹100 cr
    locations=("mumbai", "maharashtra"),
    win_categories=("storage racks",),
)


def signals(title="", text="", value=None, closing=None):
    return TenderSignals(
        title=title, text=text, value_inr=value, closing_at=closing, now=NOW
    )


def test_category_matched_tender_lands_in_our_lane():
    result = triage(
        signals(
            title="Supply of industrial storage racks",
            text="rack installation at the central warehouse, storage capacity 5000 pallets",
            value=2.4e7,
            closing=NOW + timedelta(days=11),
        ),
        PROFILE,
    )
    assert result.radar_list == "in_our_lane"
    assert result.matched_category == "storage racks"
    assert result.fit_score > 0.7
    assert result.band == "green"
    assert result.checkpoint0 == "auto_passed"  # confident + List A auto-passes
    assert any("category 'storage racks' matched 100%" in r for r in result.reasons)
    assert any("closes in 11 days" in r for r in result.reasons)
    assert any("won in this category before" in r for r in result.reasons)


def test_unmatched_category_with_strong_signals_lands_on_radar():
    result = triage(
        signals(
            title="Procurement of CT scanners for civil hospital, Mumbai",
            text="medical imaging equipment, installation and maintenance in Mumbai",
            value=5e7,
            closing=NOW + timedelta(days=20),
        ),
        PROFILE,
    )
    assert result.radar_list == "opportunity_radar"
    assert result.checkpoint0 == "queued"  # List B never auto-passes
    assert any("no category match" in r for r in result.reasons)
    assert any("₹5.00 cr" in r for r in result.reasons)
    assert any("location matches" in r for r in result.reasons)


def test_low_information_tender_queues_for_human():
    # No value, no closing date, no category signal: never guess (§9 rule 3).
    result = triage(signals(title="Corrigendum 4", text="see attachment"), PROFILE)
    assert result.radar_list == "needs_human"
    assert result.checkpoint0 == "queued"
    assert result.band in ("yellow", "red")
    assert any("queued for a human" in r for r in result.reasons)


def test_borderline_fit_queues_for_human():
    # Category matches 3/4 keywords, nothing else known: fit lands just
    # under the in-lane threshold — inside the margin, so a human decides.
    profile = OrgProfile(
        categories=(Category("cabinets", ("steel", "cabinet", "office", "modular")),),
        win_categories=(),
    )
    result = triage(
        signals(title="Steel office cabinet supply"), profile, Thresholds()
    )
    assert result.radar_list == "needs_human"
    assert any("borderline" in r for r in result.reasons)


def test_weights_come_from_config_not_code():
    tender = signals(
        title="Supply of industrial storage racks",
        value=2.4e7,
        closing=NOW + timedelta(days=11),
    )
    category_heavy = OrgProfile(
        categories=PROFILE.categories,
        value_band_inr=PROFILE.value_band_inr,
        win_categories=(),
        weights={"category": 0.8, "eligibility": 0.05, "value": 0.05,
                 "location": 0.05, "win_history": 0.05},
    )
    value_heavy = OrgProfile(
        categories=PROFILE.categories,
        value_band_inr=PROFILE.value_band_inr,
        win_categories=(),
        weights={"category": 0.05, "eligibility": 0.05, "value": 0.8,
                 "location": 0.05, "win_history": 0.05},
    )
    fit_a = triage(tender, category_heavy).fit_score
    fit_b = triage(tender, value_heavy).fit_score
    assert fit_a != fit_b, "changing config weights must change the fit"


def test_unknown_components_lower_confidence_not_score():
    full = triage(
        signals(title="storage rack warehouse", value=2e7,
                closing=NOW + timedelta(days=5)),
        PROFILE,
    )
    sparse = triage(signals(title="storage rack warehouse"), PROFILE)
    assert sparse.confidence < full.confidence
    assert sparse.components["value"] is None
    assert sparse.components["eligibility"] is None


def test_extract_value_inr_is_regex_only():
    assert extract_value_inr("Tender Value: Rs 2,40,00,000") == 2.4e7
    assert extract_value_inr("estimated cost ₹2.4 crore") == 2.4e7
    assert extract_value_inr("EMD Rs 50,000; contract value Rs 5 crore") == 5e7
    assert extract_value_inr("value approx ₹75 lakh") == 75e5
    assert extract_value_inr("no numbers here") is None
    assert extract_value_inr("") is None


# --- The two lists must actually be usable ----------------------------------


def _profile(**over):
    """A profile whose weight keys match the scorer's component names."""
    base = dict(
        categories=(Category("storage racks", ("rack", "racking", "storage")),),
        weights={
            "category": 0.35, "eligibility": 0.25, "value": 0.15,
            "location": 0.10, "win_history": 0.15,
        },
        value_band_inr=(100_000, 50_000_000_000),
        win_categories=("storage racks",),
    )
    base.update(over)
    return OrgProfile(**base)


def test_unrecognised_weight_keys_cannot_wreck_confidence():
    """The live bug: the org profile used category_fit / value_band / past_wins,
    which the scorer never reads. They were merged in anyway and counted in
    `total_weight` — the denominator of coverage — so coverage halved to 0.45,
    fell under the 0.50 floor, and EVERY tender was pinned in the needs-human
    queue. Both radar lists were permanently empty.

    The service layer now drops unknown keys; this pins the arithmetic itself.
    """
    from app.services.triage import _known_weights

    assert _known_weights(
        {"category_fit": 0.4, "value_band": 0.3, "past_wins": 0.3}
    ) == {}
    assert _known_weights({"category": 0.5, "value": 0.5}) == {
        "category": 0.5, "value": 0.5
    }


def test_a_poor_fit_is_not_presented_as_an_opportunity():
    """`triage_radar_threshold` was consulted only for the borderline check, so
    the final branch swept everything into the opportunity radar. A PNB request
    for "suitable ready premises" scored 0.10 and was shown as an opportunity
    Godrej could win."""
    from bidproof_triage import NOT_RELEVANT, OPPORTUNITY_RADAR

    signals = TenderSignals(
        title="Punjab National Bank requires suitable ready premises on lease",
        text="",
        value_inr=None,
        closing_at=datetime(2026, 12, 1, tzinfo=timezone.utc),
        now=datetime(2026, 7, 30, tzinfo=timezone.utc),
    )
    result = triage(signals, _profile(), Thresholds())
    assert result.radar_list != OPPORTUNITY_RADAR, result.reasons
    assert result.radar_list in {NOT_RELEVANT, "needs_human"}


def test_a_real_match_still_reaches_in_our_lane():
    """The fix must not empty the lists a different way."""
    from bidproof_triage import IN_OUR_LANE

    signals = TenderSignals(
        title="Supply and installation of heavy duty pallet racking storage system",
        text="Estimated value Rs 10,00,00,000. Racking to EN 15512.",
        value_inr=100_000_000,
        closing_at=datetime(2026, 12, 1, tzinfo=timezone.utc),
        now=datetime(2026, 7, 30, tzinfo=timezone.utc),
    )
    result = triage(signals, _profile(), Thresholds())
    assert result.radar_list == IN_OUR_LANE, (result.radar_list, result.reasons)
    assert result.fit_score >= 0.55

# --- The deadline reason perishes; every other reason is a durable fact. ---
#
# Regression, seen live on 2026-08-03: a CWC tender triaged on 30 July still
# explained itself with "closes in 8 days" while the countdown chip beside it
# read "4d left" — the same card contradicting itself, on the one number a
# bidder cannot afford to misread. SPEC section 3.2 (List B) frames the reason list
# as the card explaining itself *now*, so the phrase must track today, not the
# day the tender happened to be discovered.

MYSORE_CLOSE = datetime(2026, 8, 7, 15, 0, tzinfo=timezone.utc)


def test_deadline_reason_tracks_today_not_the_day_of_triage():
    triaged_on = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
    assert deadline_reason(MYSORE_CLOSE, triaged_on) == "closes in 8 days"

    read_on = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)
    assert deadline_reason(MYSORE_CLOSE, read_on) == "closes in 4 days"


def test_deadline_reason_covers_unknown_and_passed():
    now = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)
    assert deadline_reason(None, now) == "closing date unknown"
    assert deadline_reason(now - timedelta(days=2), now) == "closing date has passed"


STORED = [
    "category 'storage racks' matched 25%",
    "tender value unknown",
    "closes in 8 days",
    "won in this category before",
    "passes 100% of provisional checks",
]


def test_stored_reasons_are_refreshed_against_the_live_deadline():
    fresh = refresh_deadline_reason(
        STORED, MYSORE_CLOSE, datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)
    )
    # Replaced where it stood, so the card does not reshuffle as days pass.
    assert fresh[2] == "closes in 4 days"
    # The durable facts are the original triage's, untouched.
    assert fresh[:2] == STORED[:2]
    assert fresh[3:] == STORED[3:]


def test_refresh_rewrites_a_passed_deadline_and_an_unknown_one():
    now = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)

    closed = refresh_deadline_reason(STORED, datetime(2026, 8, 1, tzinfo=timezone.utc), now)
    assert closed[2] == "closing date has passed"

    # A tender discovered without a date, given one by a later corrigendum.
    was_unknown = [*STORED[:2], "closing date unknown", *STORED[3:]]
    assert refresh_deadline_reason(was_unknown, MYSORE_CLOSE, now)[2] == "closes in 4 days"


def test_refresh_appends_when_the_stored_triage_never_mentioned_a_deadline():
    without = [r for r in STORED if "closes in" not in r]
    fresh = refresh_deadline_reason(
        without, MYSORE_CLOSE, datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)
    )
    assert fresh[: len(without)] == without
    assert fresh[-1] == "closes in 4 days"


def test_refresh_leaves_an_empty_reason_list_alone():
    # No triage has run yet; inventing a lone reason would be a card that
    # explains itself with one arbitrary line.
    assert refresh_deadline_reason([], MYSORE_CLOSE, NOW) == []
