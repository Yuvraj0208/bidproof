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


# --- NIC eProcurement: one adapter, many public buyers ----------------------


def test_nic_portal_builds_the_platform_listing_url():
    """Every NIC eProcurement instance serves the same path on its own host, so a
    new public buyer is configuration rather than code."""
    from bidproof_adapters.niceproc import NicPortal

    portal = NicPortal(name="iocl", host="iocletenders.nic.in")
    assert portal.listing_url == (
        "https://iocletenders.nic.in"
        "/nicgep/app?page=FrontEndLatestActiveTenders&service=page"
    )


def test_nic_adapter_is_scoped_to_its_own_host():
    """An adapter must never widen the allow-list: that is the SSRF boundary."""
    from bidproof_adapters.niceproc import NicEprocAdapter, NicPortal

    adapter = NicEprocAdapter(NicPortal(name="ntpc", host="eprocurentpc.nic.in"))
    assert adapter.name == "ntpc"
    assert adapter.allowed_domains == ("eprocurentpc.nic.in",)


async def test_nic_adapter_refuses_a_host_outside_the_allow_list():
    from bidproof_adapters.niceproc import NicEprocAdapter, NicPortal

    adapter = NicEprocAdapter(NicPortal(name="evil", host="evil.example.com"))
    fetcher = GuardedFetcher(ALLOW)
    with pytest.raises(BlockedDomainError):
        await adapter.discover(fetcher)
    await fetcher.aclose()


async def test_nic_adapter_says_so_when_no_browser_is_installed():
    """Plain HTTP returns the page furniture with an EMPTY tender table, so
    reporting "no tenders" would be a lie. It raises instead, and the Scout
    records this one portal as failed while the others keep flowing."""
    from bidproof_adapters import niceproc
    from bidproof_adapters.niceproc import NicEprocAdapter, NicPortal

    adapter = NicEprocAdapter(NicPortal(name="iocl", host="iocletenders.nic.in"))
    fetcher = GuardedFetcher(DomainAllowList(["iocletenders.nic.in"]))
    original = niceproc.adapter.playwright_available
    niceproc.adapter.playwright_available = lambda: False
    try:
        with pytest.raises(RuntimeError, match="need a real browser"):
            await adapter.discover(fetcher)
    finally:
        niceproc.adapter.playwright_available = original
        await fetcher.aclose()


def test_malformed_portal_config_is_skipped_not_fatal():
    from app.services.discovery import parse_nic_portals

    portals = parse_nic_portals("iocl:iocletenders.nic.in, ,broken,ntpc:eprocurentpc.nic.in")
    assert [p.name for p in portals] == ["iocl", "ntpc"]


def test_nic_parser_ignores_announcements_and_navigation():
    """The first attempt reused the CPPP parser and reported IOCL's web
    announcement "Restriction in IOCL E-Tendering Portal towards the number of
    users" as a tender. A row is a tender only if it links to one."""
    from bidproof_adapters.niceproc import parse_tender_list

    html = """
    <table>
      <tr><td><a href="/nicgep/app?page=WebAnnouncements&service=page#429">
          Restriction in IOCL E-Tendering Portal towards the number of users</a></td></tr>
      <tr><td><a href="/nicgep/app?page=FrontEndAdvancedSearch&service=page">Search</a></td></tr>
      <tr>
        <td>1</td>
        <td>12-Aug-2026 15:00</td>
        <td>Supply of heavy duty pallet racking for the Panipat depot</td>
        <td>IOCL/2026/RACK/4417</td>
        <td><a href="/nicgep/app?page=FrontEndViewTender&service=page&id=9911">View</a></td>
      </tr>
    </table>
    """
    found = parse_tender_list(html, portal="iocl", base_url="https://iocletenders.nic.in/nicgep/app")

    assert len(found) == 1, [t.title for t in found]
    tender = found[0]
    assert tender.portal == "iocl"
    assert tender.title.startswith("Supply of heavy duty pallet racking")
    assert tender.external_id == "IOCL/2026/RACK/4417"
    assert tender.url.endswith("page=FrontEndViewTender&service=page&id=9911")
    assert tender.closing_at is not None
    assert (tender.closing_at.day, tender.closing_at.month) == (12, 8)


def test_nic_parser_returns_nothing_rather_than_guessing():
    """An empty listing must produce zero tenders, not site furniture."""
    from bidproof_adapters.niceproc import parse_tender_list

    html = "<table><tr><td>Tender Title</td><td>Closing Date</td></tr></table>"
    assert parse_tender_list(html, portal="ntpc", base_url="https://x/nicgep/app") == []


# --- Plain HTML tender tables: CWC and PNB ----------------------------------


CWC_ROW = """
<table>
  <tr><th>Sr.No</th><th>Work/Item Title</th><th>Tender Reference Number</th>
      <th>Location Detail</th><th>Inviting Officer</th>
      <th>Bid Sub.Closing Date</th><th>View</th></tr>
  <tr><td colspan="7">Sort by Relevance Date</td></tr>
  <tr>
    <td>1</td>
    <td>Appointment of Strategic Alliance Management Operator for ICD Valvada</td>
    <td>CWC/RO-AHD/BUSI.(Proj.)-75(2022)/SAMO/ICD-VALVADA/2026-27</td>
    <td>CWC-ICD VALVADA, UMBERGAON (VALSAD), GUJARAT,</td>
    <td>RM,CWC,RO,Ahmedabad</td>
    <td>24-08-2026 03:00:00 PM</td>
    <td><a href="/Home/ViewTenderData?TenderID=teYAgznZDJ%2FCsY5NCag7DA%3D%3D">View</a></td>
  </tr>
</table>
"""


def test_cwc_row_parses_with_a_durable_per_tender_link():
    """CWC is the only Indian portal found whose tender link is an address
    rather than a session ticket, so "open on portal" genuinely works."""
    from bidproof_adapters.htmlportal import CWC, parse_table

    found = parse_table(CWC_ROW, CWC)
    assert len(found) == 1, [t.title for t in found]
    t = found[0]
    assert t.portal == "cwc"
    assert t.title.startswith("Appointment of Strategic Alliance")
    assert t.external_id.startswith("CWC/RO-AHD")
    assert t.url == (
        "https://cewacor.nic.in/Home/ViewTenderData"
        "?TenderID=teYAgznZDJ%2FCsY5NCag7DA%3D%3D"
    )
    assert t.closing_at is not None
    assert (t.closing_at.day, t.closing_at.month, t.closing_at.hour) == (24, 8, 15)
    assert "VALVADA" in (t.organisation or "")


def test_header_and_control_rows_are_not_tenders():
    """The "Sort by Relevance" control row and the header must not become
    tenders — the mistake that turned an IOCL announcement into one."""
    from bidproof_adapters.htmlportal import CWC, parse_table

    assert len(parse_table(CWC_ROW, CWC)) == 1


def test_pnb_row_falls_back_to_the_listing_when_no_link_exists():
    """PNB's rows are ASP.NET __doPostBack calls, so no tender has a URL. The
    card points at the listing rather than inventing a deep link."""
    from bidproof_adapters.htmlportal import PNB, parse_table

    html = """
    <table>
      <tr><td>1</td><td>CO BIKANER</td>
          <td><a href="javascript:__doPostBack('ctl00$rptGrid$ctl00$lbtnTenderTitle','')">
              OFFERs FOR PREMISES ON LEASE WITHIN THE VICINITY OF G S ROAD</a></td></tr>
    </table>
    """
    found = parse_table(html, PNB)
    assert len(found) == 1
    assert found[0].url == "https://www.pnbindia.in/Tender.aspx"
    assert "javascript" not in found[0].url
    assert found[0].closing_at is None, "PNB publishes no closing date column"


def test_an_unparseable_closing_date_stays_absent():
    """Never guess a deadline: a wrong one could lose a bid."""
    from bidproof_adapters.htmlportal.parsing import parse_closing

    assert parse_closing("24-08-2026 03:00:00 PM") is not None
    assert parse_closing("") is None
    assert parse_closing("as per portal") is None


def test_html_adapter_is_scoped_to_its_own_host():
    from bidproof_adapters.htmlportal import CWC, HtmlPortalAdapter

    adapter = HtmlPortalAdapter(CWC)
    assert adapter.name == "cwc"
    assert adapter.allowed_domains == ("cewacor.nic.in",)


async def test_html_adapter_refuses_a_host_outside_the_allow_list():
    from bidproof_adapters.htmlportal import HtmlPortalAdapter, TableProfile

    rogue = TableProfile(name="rogue", listing_url="https://evil.example.com/t", title_col=1)
    fetcher = GuardedFetcher(ALLOW)
    with pytest.raises(BlockedDomainError):
        await HtmlPortalAdapter(rogue).discover(fetcher)
    await fetcher.aclose()


# --- The browser must work under a selector event loop ----------------------


def test_render_does_not_use_the_async_playwright_api():
    """Windows + uvicorn is a selector event loop, which cannot spawn
    subprocesses — so `async_playwright()` dies with a bare NotImplementedError.
    A live discovery run recorded exactly that: `gem: NotImplementedError` while
    cppp succeeded, so every browser adapter was broken inside the API while
    working fine from a script.

    The renderer therefore uses Playwright's SYNC api on a worker thread, which
    launches its driver with plain `subprocess` and ignores the loop type. This
    pins that: reintroducing `async_playwright` would break the API again.
    """
    from pathlib import Path

    import bidproof_adapters.browser as browser

    source = Path(browser.__file__).read_text(encoding="utf-8")
    # Match the IMPORT, not the word — the docstring explains why the async API
    # is avoided, and that explanation should stay.
    assert "playwright.async_api" not in source, (
        "async_playwright cannot launch under uvicorn's SelectorEventLoop"
    )
    assert "playwright.sync_api" in source
    assert "to_thread" in source, "the blocking render must not block the loop"


async def test_render_still_refuses_an_off_allow_list_url_before_launching():
    """The guard runs before any browser starts — no process is spawned for a
    host we are not allowed to visit."""
    from bidproof_adapters.browser import render

    fetcher = GuardedFetcher(ALLOW)
    with pytest.raises(BlockedDomainError):
        await render("https://evil.example.com/tenders", fetcher)
    await fetcher.aclose()
