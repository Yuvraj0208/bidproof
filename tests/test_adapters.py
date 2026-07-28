"""US-01 unit tests: the SSRF domain guard, portal parsers, and the Scout's
adapter isolation."""

from pathlib import Path

import httpx
import pytest

from bidproof_adapters import (
    BlockedDomainError,
    DiscoveredTender,
    DomainAllowList,
    GuardedFetcher,
)
from bidproof_adapters.cppp.parsing import parse_feed
from bidproof_adapters.gem.parsing import parse_bid_cards
from bidproof_scout import run_adapters

FIXTURES = Path(__file__).parent / "fixtures"

ALLOW = DomainAllowList(["gem.gov.in", "eprocure.gov.in", "portal.test"])


# --- The guard: Scout may ONLY reach the portal allow-list ------------------


def test_guard_blocks_unlisted_domain():
    with pytest.raises(BlockedDomainError):
        ALLOW.check("https://evil.example.com/tender.pdf")


def test_guard_blocks_ssrf_targets():
    for url in (
        "http://169.254.169.254/latest/meta-data/",   # cloud metadata
        "http://127.0.0.1:8000/health",
        "http://10.0.0.5/internal",
        "http://localhost:9001/console",
        "http://[::1]/",
        "file:///etc/passwd",
        "ftp://eprocure.gov.in/feed",                 # right host, wrong scheme
    ):
        with pytest.raises(BlockedDomainError):
            ALLOW.check(url)


def test_guard_allows_listed_domains_and_subdomains():
    ALLOW.check("https://eprocure.gov.in/cppp/latestactivetendersnew")
    ALLOW.check("https://bidplus.gem.gov.in/all-bids")
    # suffix-in-the-middle must NOT pass
    with pytest.raises(BlockedDomainError):
        ALLOW.check("https://gem.gov.in.attacker.io/x")


async def test_fetcher_never_sends_blocked_requests():
    sent: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(str(request.url))
        return httpx.Response(200, content=b"ok")

    fetcher = GuardedFetcher(
        ALLOW, client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(BlockedDomainError):
        await fetcher.get("https://attacker.io/steal")
    assert sent == [], "a blocked URL must never reach the transport"

    response = await fetcher.get("https://portal.test/feed.xml")
    assert response.status_code == 200
    assert sent == ["https://portal.test/feed.xml"]


# --- Portal parsers ---------------------------------------------------------


def test_cppp_feed_parses_tenders_and_skips_malformed():
    tenders = parse_feed((FIXTURES / "cppp_feed.xml").read_text(encoding="utf-8"))

    assert len(tenders) == 2  # the malformed third item is skipped, not guessed
    first = tenders[0]
    assert first.portal == "cppp"
    assert first.external_id == "2026_DOS_112233_1"
    assert "Modular Office Furniture" in first.title
    assert first.url.startswith("https://eprocure.gov.in/")
    assert first.closing_at is not None
    assert (first.closing_at.day, first.closing_at.month) == (5, 8)
    assert first.organisation == "Department of Space"


def test_cppp_html_listing_parses_live_portal_shape():
    from bidproof_adapters.cppp.parsing import parse_listing

    html = (FIXTURES / "cppp_page.html").read_text(encoding="utf-8")
    tenders = parse_listing(html)

    assert len(tenders) == 2  # the broken row is skipped, never guessed
    first = tenders[0]
    assert first.external_id == "136762"  # trailing Tender Id = dedup key
    assert first.title == "PAINTING WORKS ATF CONVERSION VASHI"
    assert first.url.endswith("/tendersfullview/OPAQUE1")
    assert first.organisation == "Hindustan Petroleum Corporation Limited"
    assert (first.closing_at.day, first.closing_at.month, first.closing_at.hour) == (3, 8, 15)
    assert tenders[1].external_id == "2026_MCL_362232_1"


def test_gem_bid_cards_parse_and_ignore_cardless_noise():
    html = (FIXTURES / "gem_bids.html").read_text(encoding="utf-8")
    tenders = parse_bid_cards(html, base_url="https://bidplus.gem.gov.in/all-bids")

    assert [t.external_id for t in tenders] == [
        "GEM/2026/B/7811223",
        "GEM/2026/B/7815566",
    ]
    assert tenders[0].title == "Supply of Steel Storage Cabinets - Ministry of Defence"
    assert tenders[0].url == "https://bidplus.gem.gov.in/showbidDocument/7811223"
    assert tenders[0].closing_at is not None
    assert (tenders[0].closing_at.day, tenders[0].closing_at.month) == (31, 7)


# --- Scout isolation: one adapter throwing does not stop the others ---------


class HealthyAdapter:
    name = "healthy"
    allowed_domains = ("portal.test",)

    async def discover(self, fetcher):
        return [
            DiscoveredTender(
                portal=self.name,
                external_id="T-1",
                title="Healthy tender",
                url="https://portal.test/t/1",
            )
        ]


class ExplodingAdapter:
    name = "exploding"
    allowed_domains = ("portal.test",)

    async def discover(self, fetcher):
        raise RuntimeError("portal redesigned its markup overnight")


class ImportBrokenAdapter:
    name = "import-broken"
    allowed_domains = ("portal.test",)

    async def discover(self, fetcher):
        import a_module_that_does_not_exist  # noqa: F401

        return []


async def test_one_adapter_throwing_does_not_stop_the_others():
    fetcher = GuardedFetcher(
        ALLOW,
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(200))
        ),
    )
    report = await run_adapters(
        [ExplodingAdapter(), HealthyAdapter(), ImportBrokenAdapter()], fetcher
    )

    assert [r.adapter for r in report.runs] == ["exploding", "healthy", "import-broken"]
    assert report.failed_adapters == ["exploding", "import-broken"]
    assert [t.external_id for t in report.tenders] == ["T-1"]
    failed = report.runs[0]
    assert not failed.ok
    assert "portal redesigned" in failed.error


# --- GeM documents are durable; CPPP links are session tickets ---------------


def test_gem_card_exposes_the_document_link_as_pdf_url():
    """GeM serves `/showbidDocument/<id>` as application/pdf with no session,
    cookie or captcha (verified live 2026-07-26). That link IS the document, so
    discovery can attach it and the tender arrives readable instead of as bare
    metadata."""
    html = (FIXTURES / "gem_bids.html").read_text(encoding="utf-8")
    tenders = parse_bid_cards(html, base_url="https://bidplus.gem.gov.in/all-bids")

    assert tenders[0].pdf_url == "https://bidplus.gem.gov.in/showbidDocument/7811223"
    assert all(t.pdf_url for t in tenders)


def test_gem_card_without_a_document_link_claims_no_pdf():
    """No link means no document. The parser never invents one (§9 rule 3)."""
    html = (
        '<div class="card"><span>GEM/2026/B/9999999</span>'
        '<div data-title="Bid with no document yet"></div></div>'
    )
    tenders = parse_bid_cards(html, base_url="https://bidplus.gem.gov.in/all-bids")

    assert len(tenders) == 1
    assert tenders[0].pdf_url is None


async def test_cppp_falls_back_to_plain_http_without_a_browser():
    """Playwright missing must degrade this ONE adapter, never fail discovery."""
    from bidproof_adapters.cppp.adapter import CpppAdapter

    feed = (FIXTURES / "cppp_page.html").read_text(encoding="utf-8")

    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, text=feed)

    fetcher = GuardedFetcher(
        ALLOW, client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    # use_browser=False is the same path a missing Playwright install takes.
    tenders = await CpppAdapter(use_browser=False).discover(fetcher)

    assert calls, "the plain-HTTP fallback should have been used"
    assert tenders, "the listing should still parse without a browser"
    await fetcher.aclose()


async def test_cppp_still_refuses_an_off_portal_feed_url():
    """The allow-list is checked before either path runs."""
    from bidproof_adapters.cppp.adapter import CpppAdapter

    fetcher = GuardedFetcher(ALLOW)
    with pytest.raises(BlockedDomainError):
        await CpppAdapter(
            "https://evil.example.com/feed", use_browser=False
        ).discover(fetcher)
    await fetcher.aclose()
