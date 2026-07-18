"""GeM adapter — the bid list is JS-rendered, so it needs Playwright
(optional `gem` extra; `playwright install chromium` once).

Isolation and least privilege:
- Playwright is imported lazily. If it is missing, `discover` raises and the
  Scout records THIS adapter as failed while every other adapter continues.
- The browser context blocks every request whose host fails the same
  allow-list the GuardedFetcher enforces — the browser cannot be steered
  off the portal, even by the portal's own markup.
"""

from bidproof_adapters.contract import DiscoveredTender
from bidproof_adapters.gem.parsing import parse_bid_cards
from bidproof_adapters.guard import BlockedDomainError, GuardedFetcher

DEFAULT_BIDS_URL = "https://bidplus.gem.gov.in/all-bids"


def playwright_available() -> bool:
    try:
        import playwright  # noqa: F401

        return True
    except ImportError:
        return False


class GemAdapter:
    name = "gem"
    allowed_domains = ("gem.gov.in",)  # covers bidplus.gem.gov.in etc.

    def __init__(self, bids_url: str = DEFAULT_BIDS_URL) -> None:
        self._bids_url = bids_url

    async def discover(self, fetcher: GuardedFetcher) -> list[DiscoveredTender]:
        fetcher.allowlist.check(self._bids_url)
        html = await self._render_page(fetcher)
        return parse_bid_cards(html, base_url=self._bids_url)

    async def _render_page(self, fetcher: GuardedFetcher) -> str:
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                context = await browser.new_context()

                async def enforce_allowlist(route):
                    try:
                        fetcher.allowlist.check(route.request.url)
                    except BlockedDomainError:
                        await route.abort()
                    else:
                        await route.continue_()

                await context.route("**/*", enforce_allowlist)
                page = await context.new_page()
                await page.goto(self._bids_url, wait_until="networkidle")
                return await page.content()
            finally:
                await browser.close()
