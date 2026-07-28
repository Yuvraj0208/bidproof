"""GeM adapter — the bid list is JS-rendered, so it needs Playwright
(optional `gem` extra; `playwright install chromium` once).

Unlike CPPP, GeM publishes its bid documents as plain, durable PDFs:
`bidplus.gem.gov.in/showbidDocument/<id>` answers with `application/pdf` and no
session, cookie or captcha (verified live 2026-07-26). So GeM tenders can arrive
with a real document attached, which is why `parse_bid_cards` fills `pdf_url`.

Isolation and least privilege live in `bidproof_adapters.browser`: Playwright is
imported lazily, and every request the page makes is checked against the same
allow-list the GuardedFetcher enforces.
"""

from bidproof_adapters.browser import playwright_available, render  # noqa: F401
from bidproof_adapters.contract import DiscoveredTender
from bidproof_adapters.gem.parsing import parse_bid_cards
from bidproof_adapters.guard import GuardedFetcher

DEFAULT_BIDS_URL = "https://bidplus.gem.gov.in/all-bids"

# Stable entry point for a human to search from, when a specific bid link is
# no longer good.
SEARCH_URL = DEFAULT_BIDS_URL


class GemAdapter:
    name = "gem"
    allowed_domains = ("gem.gov.in",)  # covers bidplus.gem.gov.in etc.

    def __init__(self, bids_url: str = DEFAULT_BIDS_URL) -> None:
        self._bids_url = bids_url

    async def discover(self, fetcher: GuardedFetcher) -> list[DiscoveredTender]:
        fetcher.allowlist.check(self._bids_url)
        html = await render(self._bids_url, fetcher)
        return parse_bid_cards(html, base_url=self._bids_url)
