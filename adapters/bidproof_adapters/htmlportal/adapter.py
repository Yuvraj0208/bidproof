"""Discovery for buyers that publish an ordinary HTML tender table.

Both known portals render their table with JavaScript (CWC) or ASP.NET postbacks
(PNB), so plain HTTP returns zero rows — this uses the shared Playwright renderer
and the same allow-list guard as every other adapter.

Neither portal is captcha-gated, and neither is disallowed by robots.txt for
these pages. Bank of Baroda's robots.txt does disallow every `*.pdf`, which is
why no adapter here ever fetches a document: the listing and the link out are the
whole job, as they are for CPPP.
"""

import logging

from bidproof_adapters.browser import playwright_available, render
from bidproof_adapters.contract import DiscoveredTender
from bidproof_adapters.guard import GuardedFetcher
from bidproof_adapters.htmlportal.parsing import TableProfile, parse_table

logger = logging.getLogger(__name__)


# --- Portal profiles, verified live 2026-07-30 -------------------------------

# Central Warehousing Corporation. The highest category match Godrej has —
# warehouses mean racking — and the only portal found with a DURABLE per-tender
# link, so "open on portal" actually works here.
CWC = TableProfile(
    name="cwc",
    listing_url="https://cewacor.nic.in/Home/TenderList",
    title_col=1,
    reference_col=2,
    location_col=3,
    closing_col=5,
    detail_link_marker="ViewTenderData",
    min_cells=6,
)

# Punjab National Bank. Banks buy safes, vaults and lockers — the Security
# Solutions category, which had no source at all. Its rows link via
# `__doPostBack`, so no tender has its own URL: every card points at the
# listing, which is the honest best available.
PNB = TableProfile(
    name="pnb",
    listing_url="https://www.pnbindia.in/Tender.aspx",
    title_col=2,
    location_col=1,
    min_cells=3,
)

PROFILES: dict[str, TableProfile] = {p.name: p for p in (CWC, PNB)}


class HtmlPortalAdapter:
    """One portal publishing a tender table. Isolation per SPEC §20: this one
    failing is recorded against this portal alone."""

    def __init__(self, profile: TableProfile) -> None:
        self._profile = profile
        self.name = profile.name
        host = profile.listing_url.split("/")[2]
        # Only this portal's host — an adapter never widens the allow-list.
        self.allowed_domains = (host,)

    async def discover(self, fetcher: GuardedFetcher) -> list[DiscoveredTender]:
        url = self._profile.listing_url
        fetcher.allowlist.check(url)

        if not playwright_available():
            # Plain HTTP returns the page with an EMPTY table on both portals, so
            # "no tenders" would be a lie. Fail loudly for this portal instead.
            raise RuntimeError(
                f"{self.name}: this portal renders its table with JavaScript and "
                "needs a browser (playwright install chromium)"
            )

        html = await render(url, fetcher)
        tenders = parse_table(html, self._profile)
        if not tenders:
            logger.warning(
                "%s: rendered %d bytes but parsed no tenders — the table layout "
                "may have changed", self.name, len(html)
            )
        return tenders
