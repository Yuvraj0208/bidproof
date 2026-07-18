# Agent: Scout

| Field | Value |
|---|---|
| **Name** | Scout |
| **Single job** | Watch tender portals through isolated adapters, discover new tenders, and hand their documents to the shared ingest pipeline. Nothing else. |
| **Inputs** | The registered portal adapters and a `GuardedFetcher` (its only network capability). |
| **Outputs** | `DiscoveryReport`: per-adapter outcome (ok/failed, error, tenders found, duration). Discovered tenders are typed `DiscoveredTender` records — data, never instructions. |
| **Model role** | none — pure code. (Triage/fit-scoring is a different agent, US-02.) |
| **Tools** | `GuardedFetcher` restricted to the allow-list of portal domains ONLY (blocks SSRF: foreign domains, IP literals, localhost, non-http schemes). It cannot export, email, submit, or delete — it cannot even reach a non-portal URL. |
| **Guardrails** | Per-adapter isolation: one adapter throwing (or missing its optional deps) is recorded as a failed run and the rest continue. Downloads are size-capped and must pass the PDF magic-byte check before entering the pipeline. Dedup by `(org, portal, external_id)` and by document sha256. |
| **Test set** | `tests/test_adapters.py`, `tests/test_discovery_api.py` |

**Portals:** GeM (Playwright — needs the `gem` extra of `bidproof-adapters` plus
`playwright install chromium`; reviewed licence Apache-2.0) and CPPP/eprocure
(plain HTTP feed). Portal URLs are env-overridable; a portal changing its
markup breaks exactly one adapter, whose failure is visible in the discovery
run report while every other source keeps flowing (SPEC §20).
