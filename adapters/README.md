# adapters/

Isolated portal adapters (SPEC §5.1, §20): GeM via Playwright, CPPP via HTTP.
Built in US-01.

Contract:
- Each adapter lives in its own folder behind a common interface; one site
  changing must never break the rest.
- Adapters may reach ONLY an allow-list of portal domains (blocks SSRF).
- An adapter that throws is contained — the scheduler and the other adapters
  keep running, and its health shows on the Admin screen.
