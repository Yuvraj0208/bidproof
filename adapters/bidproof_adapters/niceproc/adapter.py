"""One adapter for every NIC eProcurement portal.

Most Indian public buyers do not run bespoke tender software — they run
**NIC eProcurement**, the same platform as eprocure.gov.in, on their own host.
Verified live 2026-07-30: IOCL, NTPC and Coal India all answer at

    https://<host>/nicgep/app?page=FrontEndLatestActiveTenders&service=page

with the identical page furniture, the identical "Tender Title" table header, and
the identical session behaviour. So adding a portal is a line of configuration,
not a new adapter — which is the only way a list like Godrej's (Railways, banks,
seven PSUs, metros, airports, hospitals) is ever maintainable.

What this buys, honestly:

* **Listing metadata only.** Reconnaissance showed the tender rows do not arrive
  over plain HTTP even with a JSESSIONID, and the detail page is captcha-gated
  exactly as CPPP's is (see `cppp/adapter.py`). So this renders the listing in a
  real browser and stops there. Documents are not reachable and are not
  attempted.
* **Nothing is bypassed.** A captcha is a deliberate "no automation" sign and is
  respected here as everywhere else in this codebase.

Each portal must also be added to `scout_allowed_domains`, or the guard refuses
it before a request is made — that is the SSRF boundary, and it is deliberately
not something an adapter can widen for itself.
"""

import logging
from dataclasses import dataclass

from bidproof_adapters.browser import playwright_available, render
from bidproof_adapters.contract import DiscoveredTender
from bidproof_adapters.niceproc.parsing import parse_tender_list
from bidproof_adapters.guard import GuardedFetcher

logger = logging.getLogger(__name__)

# The listing path every NIC eProcurement instance serves.
LISTING_PATH = "/nicgep/app?page=FrontEndLatestActiveTenders&service=page"


@dataclass(frozen=True)
class NicPortal:
    """One buyer running NIC eProcurement.

    `name` becomes the tender's `source`, so it must be stable — it is half of
    the dedup key (`source` + `external_id`).
    """

    name: str
    host: str
    label: str = ""

    @property
    def listing_url(self) -> str:
        return f"https://{self.host}{LISTING_PATH}"

    @property
    def base_url(self) -> str:
        return f"https://{self.host}/nicgep/app"


class NicEprocAdapter:
    """Discovery for a single NIC eProcurement portal.

    One instance per portal. Isolation is per SPEC §20: this adapter failing —
    a portal down, its markup changed, Playwright missing — is recorded against
    that portal alone and every other source keeps flowing.
    """

    def __init__(self, portal: NicPortal) -> None:
        self._portal = portal
        self.name = portal.name
        # Only this portal's host. An adapter never widens the allow-list.
        self.allowed_domains = (portal.host,)

    async def discover(self, fetcher: GuardedFetcher) -> list[DiscoveredTender]:
        url = self._portal.listing_url
        fetcher.allowlist.check(url)

        if not playwright_available():
            # Honest degradation: plain HTTP returns the page furniture with an
            # empty tender table, so reporting nothing is truthful. Claiming
            # "no tenders" when we simply could not look would not be.
            raise RuntimeError(
                f"{self.name}: NIC eProcurement listings need a real browser; "
                "install the 'gem' extra (playwright install chromium)"
            )

        html = await render(url, fetcher)
        tenders = parse_tender_list(
            html, portal=self.name, base_url=self._portal.base_url
        )
        if not tenders:
            logger.warning(
                "%s: rendered %d bytes but parsed no tenders — the listing "
                "markup may have changed", self.name, len(html)
            )
        return tenders
