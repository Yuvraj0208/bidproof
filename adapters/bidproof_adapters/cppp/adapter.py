"""CPPP (eprocure.gov.in) adapter — plain HTTP through the GuardedFetcher.

The feed URL is env-overridable via the app settings; if the portal moves or
reshapes the feed, this one adapter fails visibly in the discovery report
and every other source keeps flowing (SPEC §20).
"""

from bidproof_adapters.contract import DiscoveredTender
from bidproof_adapters.cppp.parsing import parse_feed
from bidproof_adapters.guard import GuardedFetcher

DEFAULT_FEED_URL = "https://eprocure.gov.in/cppp/latestactivetendersnew"


class CpppAdapter:
    name = "cppp"
    allowed_domains = ("eprocure.gov.in",)

    def __init__(self, feed_url: str = DEFAULT_FEED_URL) -> None:
        self._feed_url = feed_url

    async def discover(self, fetcher: GuardedFetcher) -> list[DiscoveredTender]:
        response = await fetcher.get(self._feed_url)
        return parse_feed(response.text, portal=self.name)
