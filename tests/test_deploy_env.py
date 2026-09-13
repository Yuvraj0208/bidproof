"""The deploy tools derive every container setting from a handful of values a
person supplies. The derivations are where a typo becomes a 3 a.m. outage, so
they are pinned here.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "infra" / "deploy"))

import _env  # noqa: E402

NEON = "postgresql://neondb_owner:s3cr3t@ep-x-1.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"


def test_owner_url_uses_asyncpg_and_ssl_require():
    url = _env.owner_url_asyncpg(NEON)
    assert url.startswith("postgresql+asyncpg://neondb_owner:s3cr3t@ep-x-1.ap-southeast-1.aws.neon.tech/neondb?")
    assert "ssl=require" in url
    assert "sslmode" not in url and "channel_binding" not in url


def test_app_url_swaps_in_the_app_role():
    url = _env.app_url_asyncpg(NEON, "p@ss")
    assert url.startswith("postgresql+asyncpg://bidproof_app:p@ss@ep-x-1.ap-southeast-1.aws.neon.tech/neondb?")
    assert "neondb_owner" not in url


def test_b2_region_from_endpoint():
    assert _env.b2_region("s3.us-east-005.backblazeb2.com") == "us-east-005"
    assert _env.b2_region("abc123.r2.cloudflarestorage.com") == "auto"
    assert _env.b2_region("localhost:9000") == ""


def test_space_host():
    assert _env.space_host("Yuvraj0208/bidproof") == "https://yuvraj0208-bidproof.hf.space"


def test_container_secrets_are_complete(tmp_path, monkeypatch):
    values = {
        "HF_TOKEN": "t", "HF_SPACE": "u/bidproof", "NEON_URL": NEON,
        "B2_ENDPOINT": "s3.us-east-005.backblazeb2.com", "B2_KEY_ID": "k", "B2_APP_KEY": "s",
        "APP_DB_PASSWORD": "app", "LITELLM_MASTER_KEY": "sk-x",
    }
    for key in _env.LLM_KEYS:
        values[key] = "v"
    out = _env.container_secrets(values)
    for key in ("DATABASE_URL", "DATABASE_URL_OWNER", "APP_DB_PASSWORD", "LITELLM_MASTER_KEY",
                "LITELLM_BASE_URL", "MINIO_ENDPOINT", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY",
                "MINIO_SECURE", "MINIO_REGION", "MINIO_BUCKET_RAW", "CORS_ORIGINS", *_env.LLM_KEYS):
        assert out[key], key
    assert out["MINIO_REGION"] == "us-east-005"
    assert out["LITELLM_BASE_URL"] == "http://127.0.0.1:4000"
    # No Langfuse keys -> none sent; the gateway then runs without the callback.
    assert "LANGFUSE_PUBLIC_KEY" not in out


def test_generated_values_persist(tmp_path):
    path = tmp_path / ".env.deploy"
    path.write_text("HF_TOKEN=t\n", encoding="utf-8")
    first = _env.ensure_generated(path, _env.read_env(path))
    second = _env.ensure_generated(path, _env.read_env(path))
    assert first["APP_DB_PASSWORD"] == second["APP_DB_PASSWORD"]
    assert first["LITELLM_MASTER_KEY"].startswith("sk-")
    assert "HF_TOKEN=t" in path.read_text(encoding="utf-8")
