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


@lru_cache
def get_settings() -> Settings:
    return Settings()
