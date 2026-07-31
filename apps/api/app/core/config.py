"""Settings. Everything configurable comes from env (.env in dev).

No vendor, model, or key literal may ever live in code — the defaults below
point only at local infrastructure.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # App role: RLS-constrained. Owner URL is for migrations only.
    # Port 5433 = the compose Postgres (5432 often hosts a native install).
    database_url: str = (
        "postgresql+asyncpg://bidproof_app:bidproof_app_dev@localhost:5433/bidproof"
    )
    database_url_owner: str = (
        "postgresql+asyncpg://bidproof_owner:bidproof_dev@localhost:5433/bidproof"
    )

    litellm_base_url: str = "http://localhost:4000"
    litellm_master_key: str = "dev-master-key"

    # Dev frontend origin(s), comma-separated.
    cors_origins: str = "http://localhost:5173"

    # Rupee cost per 1k tokens through the gateway; used only when the gateway
    # does not report a real cost. 0 while no hosted model is configured.
    llm_cost_per_1k_tokens_inr: float = 0.0
    # USD→INR for converting the gateway's reported per-call cost to rupees.
    usd_to_inr: float = 83.0
    # How many model calls may be in flight at once when a stage fans out over
    # independent items (the cited judge over prose rules). Sized for the
    # slowest constraint, which is usually the provider's per-minute rate limit
    # rather than our own capacity — raise it for a self-hosted model.
    llm_max_concurrency: int = 6
    # Seconds to wait on one gateway call. Extraction sends the largest prompt
    # in the product (24k characters of tender text) and a self-hosted or
    # free-tier open-weight model can take a minute or two to answer it. This
    # was hardcoded at 120s, which sat right on top of the real response time:
    # a run that took 80s once took 121s the next time and was recorded as
    # "model unavailable".
    llm_timeout_seconds: int = 300

    # Run checking through the Conductor graph instead of the sequential
    # service call. Both execute the same functions, so this is an
    # orchestration switch, not a behaviour switch — and flipping it back is
    # one environment variable if the graph misbehaves during a demo.
    conductor_enabled: bool = True

    # Object store (raw tender files).
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "bidproof"
    minio_secret_key: str = "bidproof_dev_minio"
    minio_secure: bool = False
    minio_bucket_raw: str = "tenders-raw"

    # Upload guardrails (SPEC §10 input checks).
    max_upload_mb: int = 200

    # Parser ladder thresholds + OCR cost rate (₹/page; 0 while local).
    parser_min_chars_text_page: int = 25
    parser_page_confidence_threshold: float = 0.6
    ocr_cost_per_page_inr: float = 0.0

    # Langfuse (SPEC §13). Empty keys = logging disabled, never a crash.
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3000"

    # Triage / fit score (US-02). Defaults only — each org's profile
    # (SPEC §15) overrides per tenant; the sponsor validates weights (§16).
    fit_w_category: float = 0.35
    fit_w_eligibility: float = 0.25
    fit_w_value: float = 0.15
    fit_w_location: float = 0.10
    fit_w_win_history: float = 0.15
    triage_in_lane_threshold: float = 0.55
    triage_radar_threshold: float = 0.45
    triage_confidence_floor: float = 0.5
    triage_borderline_margin: float = 0.08

    # EV configuration (SPEC §5.6) — the business numbers behind the bid
    # decision; sponsor-validated (§16), env-overridable per deployment.
    ev_p_win: float = 0.3
    ev_profit_margin_percent: float = 10.0
    ev_man_days: float = 12.0
    ev_loaded_day_rate_inr: float = 15000.0
    ev_capital_rate_annual: float = 0.12
    ev_lock_months: float = 6.0

    # Risk thresholds (SPEC §5.5) — org-level policy, sponsor-validated (§16).
    risk_pbg_max_percent: float = 5.0
    risk_emd_max_percent_of_value: float = 2.0

    # Scout (US-01). The ONLY hosts the Scout may reach (SSRF guard, SPEC §10/§11.4). Adding a
    # portal means adding it here AND to `nic_portals` below — an adapter can
    # never widen this for itself.
    scout_allowed_domains: str = (
        "gem.gov.in,eprocure.gov.in,"
        # NIC eProcurement instances, one per public buyer.
        "iocletenders.nic.in,eprocurentpc.nic.in,coalindiatenders.nic.in,"
        "tenders.ongc.co.in,cewacor.nic.in,"
        # Buyers publishing a plain HTML tender table.
        "www.pnbindia.in"
    )

    # NIC eProcurement portals to discover from, as "name:host" pairs. They all
    # run the same platform, so each is configuration rather than code — see
    # adapters/bidproof_adapters/niceproc/adapter.py.
    #
    # Deliberately NOT here:
    #   * IREPS (ireps.gov.in) — its robots.txt is "User-agent: * / Disallow: /",
    #     so the whole site is off-limits to automation. Verified 2026-07-30.
    #   * Bank portals (Bank of Baroda, PNB) — their tender pages render with
    #     JavaScript and are not NIC instances, so they need their own adapter.
    #     Bank of Baroda additionally disallows every PDF.
    nic_portals: str = (
        "iocl:iocletenders.nic.in,"
        "ntpc:eprocurentpc.nic.in,"
        "coalindia:coalindiatenders.nic.in"
    )
    # Off by default: these yield listing metadata only (the detail page is
    # captcha-gated, like CPPP), and each one is a browser render per cycle.
    nic_portals_enabled: bool = False

    # Buyers that publish an ordinary HTML tender table (adapters/htmlportal).
    # Both render with JavaScript, so each costs one browser render per cycle.
    #   cwc — Central Warehousing Corporation. Warehouses mean racking: the
    #         closest category match Godrej has. Durable per-tender links.
    #   pnb — Punjab National Bank. Banks buy safes, vaults and lockers, the
    #         Security Solutions category, which had no source at all.
    # Documents are never fetched: Bank of Baroda's robots.txt disallows every
    # PDF, so this family lists and links out, exactly as CPPP does.
    html_portals: str = "cwc,pnb"
    html_portals_enabled: bool = False
    scout_enabled: bool = False
    scout_interval_minutes: int = 60  # AC: new tenders within 4 hours
    gem_bids_url: str = "https://bidplus.gem.gov.in/all-bids"
    # Verified against the live portal 2026-07-19 (the shorter path 302s here;
    # the guard refuses redirects, so we point straight at the final URL).
    cppp_feed_url: str = "https://eprocure.gov.in/cppp/latestactivetendersnew/cpppdata"


@lru_cache
def get_settings() -> Settings:
    return Settings()
