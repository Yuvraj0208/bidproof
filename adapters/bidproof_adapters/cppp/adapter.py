"""CPPP (eprocure.gov.in) adapter.

Renders the listing in a real browser when Playwright is available, and falls
back to plain HTTP when it is not. The parsing is identical either way — the
browser buys a real portal session, not different markup.

**Why the session matters.** A CPPP detail link looks like:

    /cppp/tendersfullview/<b64 id>A13h1<b64 hash>A13h1<b64 hash>A13h1<b64 ts>...

The segments decode to a listing id, a hash, and a **unix timestamp of the
moment the listing was rendered**. Verified live on 2026-07-26: fetching such a
link without the session cookie that minted it returns *"Invalid Url.Please
Check"*, whether the link is minutes or hours old. The link is not an address;
it is a ticket. That is why `stable_portal_url` exists — a link we hand to a
human has to still work when they click it.

The feed URL is env-overridable via the app settings; if the portal moves or
reshapes the listing, this one adapter fails visibly in the discovery report and
every other source keeps flowing (SPEC §20).
"""

import logging

from bidproof_adapters.browser import playwright_available, render
from bidproof_adapters.contract import DiscoveredTender
from bidproof_adapters.cppp.parsing import parse_listing
from bidproof_adapters.guard import GuardedFetcher

logger = logging.getLogger(__name__)

DEFAULT_FEED_URL = "https://eprocure.gov.in/cppp/latestactivetendersnew/cpppdata"

# Stable entry point. Unlike a detail deep link, this one is still valid
# tomorrow — it is what a human gets sent to, with the tender reference to
# search for.
SEARCH_URL = "https://eprocure.gov.in/cppp/tendersearch"


class CpppAdapter:
    name = "cppp"
    allowed_domains = ("eprocure.gov.in",)

    def __init__(
        self, feed_url: str = DEFAULT_FEED_URL, *, use_browser: bool = True
    ) -> None:
        self._feed_url = feed_url
        self._use_browser = use_browser

    async def discover(self, fetcher: GuardedFetcher) -> list[DiscoveredTender]:
        fetcher.allowlist.check(self._feed_url)
        html = await self._load(fetcher)
        return parse_listing(html, portal=self.name)

    async def _load(self, fetcher: GuardedFetcher) -> str:
        """Browser first, plain HTTP second. Never both silently — the fallback
        is logged, because which path ran changes what the links are worth."""
        if self._use_browser and playwright_available():
            try:
                return await render(self._feed_url, fetcher)
            except Exception as exc:
                logger.warning(
                    "cppp: browser render failed (%s); falling back to plain HTTP",
                    exc,
                )
        response = await fetcher.get(self._feed_url)
        return response.text
