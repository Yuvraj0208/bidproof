"""Shared Playwright renderer for portals that will not answer plain HTTP.

Two portals need a real browser, for different reasons:

- **GeM** renders its bid list with JavaScript, so plain HTTP returns an empty
  shell.
- **CPPP** serves usable HTML, but its detail links are only valid inside the
  session that minted them (see `cppp/adapter.py`). A browser keeps that session
  the way the portal expects.

Isolation and least privilege (SPEC §10, §11.4):
- Playwright is imported lazily, so a missing install fails ONE adapter and the
  Scout records it; every other adapter keeps flowing.
- Every request the page makes is checked against the same allow-list the
  GuardedFetcher enforces, so the browser cannot be steered off the portal —
  not even by the portal's own markup. That is the SSRF and injection boundary.
- Downloads are refused. A page that tries to hand us a file is not a
  navigation, and the Scout has no business accepting one (golden rule 8).
"""

from bidproof_adapters.guard import BlockedDomainError, GuardedFetcher


def playwright_available() -> bool:
    try:
        import playwright  # noqa: F401

        return True
    except ImportError:
        return False


async def render(
    url: str,
    fetcher: GuardedFetcher,
    *,
    wait_until: str = "networkidle",
    timeout_ms: int = 45_000,
) -> str:
    """Load `url` in a headless browser and return its HTML.

    Raises whatever Playwright raises. Callers decide whether to fall back —
    the ladder principle: degrade honestly, never silently.
    """
    from playwright.async_api import async_playwright

    fetcher.allowlist.check(url)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            context = await browser.new_context(accept_downloads=False)

            async def enforce_allowlist(route):
                try:
                    fetcher.allowlist.check(route.request.url)
                except BlockedDomainError:
                    await route.abort()
                else:
                    await route.continue_()

            await context.route("**/*", enforce_allowlist)
            page = await context.new_page()
            await page.goto(url, wait_until=wait_until, timeout=timeout_ms)
            return await page.content()
        finally:
            await browser.close()
