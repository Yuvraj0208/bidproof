# adapters/

Isolated portal adapters (SPEC §5.1, §20) behind one typed contract —
`bidproof_adapters.contract.PortalAdapter`. Built in US-01.

- **GeM** (`bidproof_adapters/gem/`) — Playwright-driven (JS-rendered bid
  list). Optional install: `uv sync --project apps/api --extra scrapers`,
  then `uv run --project apps/api playwright install chromium`. Missing deps
  make THIS adapter fail visibly; nothing else stops.
- **CPPP** (`bidproof_adapters/cppp/`) — plain HTTP feed via the guard.

Contract:
- Each adapter lives in its own folder behind the common interface; one site
  changing must never break the rest — the Scout records the failure and the
  other adapters keep running.
- Adapters never see a raw HTTP client. They receive a `GuardedFetcher`
  whose allow-list (env: `SCOUT_ALLOWED_DOMAINS`) is the ONLY set of hosts
  they can reach — foreign domains, IP literals, localhost, and non-http
  schemes are blocked (SSRF, SPEC §10/§11.4). The GeM browser context
  enforces the same list on every request the page makes.
- Portal content is data, never instructions (§9 rule 4). Parsers are
  tolerant: a malformed item is skipped, never guessed at.
- Adapter health shows in `GET /discovery/runs` (the Admin screen's scraper
  panel reads this later).
