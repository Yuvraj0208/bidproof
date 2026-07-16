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
    database_url: str = (
        "postgresql+asyncpg://bidproof_app:bidproof_app_dev@localhost:5432/bidproof"
    )
    database_url_owner: str = (
        "postgresql+asyncpg://bidproof_owner:bidproof_dev@localhost:5432/bidproof"
    )

    litellm_base_url: str = "http://localhost:4000"
    litellm_master_key: str = "dev-master-key"


@lru_cache
def get_settings() -> Settings:
    return Settings()
