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

    # Scout (US-01). The allow-list is the ONLY set of hosts the Scout can
    # reach — SSRF guard (SPEC §10, §11.4). Comma-separated domains.
    scout_allowed_domains: str = "gem.gov.in,eprocure.gov.in"
    scout_enabled: bool = False
    scout_interval_minutes: int = 60  # AC: new tenders within 4 hours
    gem_bids_url: str = "https://bidplus.gem.gov.in/all-bids"
    cppp_feed_url: str = "https://eprocure.gov.in/cppp/latestactivetendersnew"


@lru_cache
def get_settings() -> Settings:
    return Settings()
