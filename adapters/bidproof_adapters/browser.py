"""Shared Playwright renderer for portals that will not answer plain HTTP.

Several portals need a real browser, for different reasons:

- **GeM** renders its bid list with JavaScript, so plain HTTP returns an empty
  shell.
- **CWC / PNB** publish an HTML table built by JavaScript or ASP.NET postbacks.
- **CPPP** serves usable HTML, but its detail links are only valid inside the
  session that minted them (see `cppp/adapter.py`). A browser keeps that session.

**Why the SYNC Playwright API, in a thread.** On Windows, uvicorn installs
`asyncio.SelectorEventLoop` (uvicorn/loops/asyncio.py), and a selector loop
cannot spawn subprocesses — so `async_playwright()` fails with a bare
`NotImplementedError` and every browser adapter dies inside the API while working
perfectly from a standalone script. That is exactly what happened: a live
discovery run recorded `gem: NotImplementedError` while cppp succeeded.

Playwright's sync API launches its driver with plain `subprocess`, so it does not
care which asyncio loop is installed. Running it via `asyncio.to_thread` keeps
`render()` awaitable and works on every platform and loop type.

Isolation and least privilege (SPEC §10, §11.4):
- Playwright is imported lazily, so a missing install fails ONE adapter and the
  Scout records it; every other adapter keeps flowing.
- Every request the page makes is checked against the same allow-list the
  GuardedFetcher enforces, so the browser cannot be steered off the portal —
  not even by the portal's own markup. That is the SSRF and injection boundary.
- Downloads are refused. A page that tries to hand us a file is not a
  navigation, and the Scout has no business accepting one (golden rule 8).
"""

import asyncio
import logging

from bidproof_adapters.guard import BlockedDomainError, DomainAllowList, GuardedFetcher

logger = logging.getLogger(__name__)


def playwright_available() -> bool:
    try:
        import playwright  # noqa: F401

        return True
    except ImportError:
        return False


def _render_sync(
    url: str, allowlist: DomainAllowList, wait_until: str, timeout_ms: int
) -> str:
    """Blocking render. Runs in a worker thread; see the module docstring."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            context = browser.new_context(accept_downloads=False)

            def enforce_allowlist(route):
                try:
                    allowlist.check(route.request.url)
                except BlockedDomainError:
                    route.abort()
                else:
                    route.continue_()

            context.route("**/*", enforce_allowlist)
            page = context.new_page()
            page.goto(url, wait_until=wait_until, timeout=timeout_ms)
            return page.content()
        finally:
            browser.close()


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
    fetcher.allowlist.check(url)
    return await asyncio.to_thread(
        _render_sync, url, fetcher.allowlist, wait_until, timeout_ms
    )
