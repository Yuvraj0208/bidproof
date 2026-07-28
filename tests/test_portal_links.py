"""A link we show a human has to still work when they click it.

The bug these pin down was live: the radar's "Open on portal" handed the user a
CPPP deep link, and the portal answered *"Invalid Url.Please Check"*. The link
was never an address — it encodes a hash and the unix timestamp of the moment the
listing was rendered, and it only resolves inside the session that minted it.
"""

from app.services.portal_links import (
    CPPP_SEARCH,
    GEM_SEARCH,
    is_ephemeral,
    portal_hint,
    portal_search_url,
    requires_captcha,
    stable_portal_url,
)

# A real link as scraped on 2026-07-26. Its segments decode to
# 13984622 / <hash> / <hash> / 1785012896 / GEM/2026/B/7704484 / 2000 — the
# fourth being a unix timestamp. Fetching it later returns "Invalid Url".
EXPIRED_CPPP = (
    "https://eprocure.gov.in/cppp/tendersfullview/MTM5ODQ2MjI=A13h1OGQ2NzAxYTMw"
    "ZTJhNTIxMGNiNmEwM2EzNmNhYWZhODk=A13h1MTc4NTAxMjg5Ng==A13h1MjAwMA=="
)
GEM_DOCUMENT = "https://bidplus.gem.gov.in/showbidDocument/9537308"


def test_a_cppp_deep_link_is_recognised_as_a_ticket_not_an_address():
    assert is_ephemeral(EXPIRED_CPPP)


def test_a_gem_document_link_is_durable():
    assert not is_ephemeral(GEM_DOCUMENT)
    assert stable_portal_url("gem", GEM_DOCUMENT) == GEM_DOCUMENT
    # It works, so there is nothing to explain.
    assert portal_hint("gem", "GEM/2026/B/7704484", GEM_DOCUMENT) is None


def test_cppp_offers_no_direct_link_at_all():
    """Not even the search page. A link labelled "open the tender" must open the
    tender — pointing every CPPP row at the same captcha form was its own bug."""
    assert stable_portal_url("cppp", EXPIRED_CPPP) is None
    # The manual route still exists, but separately and labelled.
    assert portal_search_url("cppp") == CPPP_SEARCH
    assert requires_captcha("cppp")


def test_the_hint_names_the_reference_to_search_for():
    hint = portal_hint("cppp", "2026_MES_773519_2", EXPIRED_CPPP)
    assert hint is not None
    assert "2026_MES_773519_2" in hint
    # It must name the real obstacle, so nobody hunts for a link that cannot
    # exist, and must not imply the TENDER is closed.
    assert "captcha" in hint.lower()
    assert "closed" not in hint.lower() and "expired tender" not in hint.lower()


def test_the_hint_survives_a_tender_with_no_reference():
    hint = portal_hint("cppp", None, EXPIRED_CPPP)
    assert hint is not None
    assert "search cppp" in hint.lower()
    assert "captcha" in hint.lower()


def test_a_tender_with_no_portal_url_has_no_direct_link():
    assert stable_portal_url("cppp", None) is None
    assert stable_portal_url("gem", None) is None
    # ...but both portals still have a manual entry point.
    assert portal_search_url("cppp") == CPPP_SEARCH
    assert portal_search_url("gem") == GEM_SEARCH
    # GeM's search needs no captcha; CPPP's does.
    assert not requires_captcha("gem")


def test_a_manual_upload_has_no_portal_to_offer():
    assert stable_portal_url("manual", None) is None
    assert portal_search_url("manual") is None
    assert not requires_captcha("manual")


def test_a_scraped_url_pointing_off_portal_is_never_offered_as_a_link():
    """Portal content is data, and data does not get to choose our links.

    If a portal's markup (or an attacker editing it) hands us an off-portal
    href, we must not turn it into something the user clicks (SPEC §11.1).
    """
    assert stable_portal_url("cppp", "https://evil.example.com/pay") is None
    assert stable_portal_url("gem", "http://169.254.169.254/latest/meta-data") is None


def test_a_manual_upload_is_never_told_a_link_expired():
    """A PDF someone uploaded has no portal, no reference and no expired link.

    Claiming otherwise was a real bug: every manually uploaded tender showed
    "single-use links that expire", which is meaningless for a local file.
    """
    assert portal_hint("manual", None, None) is None
    assert portal_hint("manual", "whatever.pdf", None) is None


def test_a_portal_tender_with_no_link_says_so_without_claiming_expiry():
    hint = portal_hint("gem", "GEM/2026/B/1", None)
    assert hint is not None
    assert "no direct link" in hint
    assert "expire" not in hint.lower(), "nothing expired — there was never a link"
    assert "GEM/2026/B/1" in hint


# --- Which links may be fetched at all --------------------------------------


def test_a_gem_document_link_may_be_fetched():
    from app.services.portal_links import document_url

    assert document_url("gem", GEM_DOCUMENT) == GEM_DOCUMENT


def test_nothing_else_may_be_fetched():
    """`portal_url` is scraped data. It is a fetch target only when it is both a
    known portal host and a known document path — otherwise a poisoned listing
    would turn into an SSRF primitive (SPEC §11.1)."""
    from app.services.portal_links import document_url

    assert document_url("cppp", EXPIRED_CPPP) is None
    assert document_url("manual", None) is None
    # Right path, wrong host.
    assert document_url("gem", "https://evil.example.com/showbidDocument/1") is None
    # Right host, wrong path — the bid list is not a document.
    assert document_url("gem", "https://bidplus.gem.gov.in/all-bids") is None
    # Scheme games.
    assert document_url("gem", "file:///etc/passwd") is None
    assert document_url("gem", "http://169.254.169.254/showbidDocument/1") is None
    # A lookalike host must not pass.
    assert document_url("gem", "https://gem.gov.in.evil.com/showbidDocument/1") is None
