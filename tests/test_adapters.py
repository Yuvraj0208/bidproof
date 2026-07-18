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
