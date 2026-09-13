"""Shared by the deploy tools: read .env files, derive the container's
settings from the few values a person has to supply.

No secret is printed by anything in here.
"""

from __future__ import annotations

import re
import secrets
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

REPO = Path(__file__).resolve().parents[2]
DEPLOY_ENV = REPO / ".env.deploy"
LOCAL_ENV = REPO / ".env"

# The managed services every host needs; each deploy tool checks its own extras.
REQUIRED = ("NEON_URL", "B2_ENDPOINT", "B2_KEY_ID", "B2_APP_KEY")
GENERATED = ("APP_DB_PASSWORD", "LITELLM_MASTER_KEY")
LLM_KEYS = tuple(
    f"LLM_{role}_{part}"
    for role in ("SMALL", "MID", "STRONG")
    for part in ("MODEL", "API_BASE", "API_KEY")
)


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def ensure_generated(path: Path, values: dict[str, str]) -> dict[str, str]:
    """Fill APP_DB_PASSWORD and LITELLM_MASTER_KEY once, and persist them so a
    second run derives the same URLs the database and Space already hold."""
    fresh = {}
    if not values.get("APP_DB_PASSWORD"):
        fresh["APP_DB_PASSWORD"] = secrets.token_urlsafe(24)
    if not values.get("LITELLM_MASTER_KEY"):
        fresh["LITELLM_MASTER_KEY"] = "sk-" + secrets.token_urlsafe(32)
    if not fresh:
        return values
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    for key, value in fresh.items():
        pattern = re.compile(rf"^{key}=.*$", re.MULTILINE)
        if pattern.search(text):
            text = pattern.sub(f"{key}={value}", text)
        else:
            text += f"\n{key}={value}\n"
    path.write_text(text, encoding="utf-8")
    return {**values, **fresh}


def load_deploy_env() -> dict[str, str]:
    values = read_env(DEPLOY_ENV)
    missing = [k for k in REQUIRED if not values.get(k)]
    if missing:
        raise SystemExit(
            f"{DEPLOY_ENV.name} is missing {', '.join(missing)} — "
            f"see infra/deploy/env.deploy.example"
        )
    values = ensure_generated(DEPLOY_ENV, values)
    local = read_env(LOCAL_ENV)
    missing_llm = [k for k in LLM_KEYS if not local.get(k)]
    if missing_llm:
        raise SystemExit(f".env is missing the model roles: {', '.join(missing_llm)}")
    for key in LLM_KEYS:
        values[key] = local[key]
    return values


def _split_query(url: str) -> tuple[tuple, dict[str, str]]:
    parts = urlsplit(url)
    return parts, dict(parse_qsl(parts.query))


def owner_url_asyncpg(neon_url: str) -> str:
    """Neon's libpq URL -> the SQLAlchemy/asyncpg URL the API and Alembic use.

    asyncpg spells SSL as ssl=require and does not know channel_binding, which
    newer Neon strings include.
    """
    parts, query = _split_query(neon_url)
    query.pop("sslmode", None)
    query.pop("channel_binding", None)
    query["ssl"] = "require"
    return urlunsplit(
        ("postgresql+asyncpg", parts.netloc, parts.path, urlencode(query), "")
    )


def app_url_asyncpg(neon_url: str, app_password: str) -> str:
    """Same host and database, as the RLS-constrained application role."""
    parts, query = _split_query(neon_url)
    query.pop("sslmode", None)
    query.pop("channel_binding", None)
    query["ssl"] = "require"
    host = parts.netloc.rsplit("@", 1)[-1]
    netloc = f"bidproof_app:{app_password}@{host}"
    return urlunsplit(("postgresql+asyncpg", netloc, parts.path, urlencode(query), ""))


def b2_region(endpoint: str) -> str:
    # s3.us-east-005.backblazeb2.com -> us-east-005; R2 and MinIO have none.
    match = re.match(r"s3\.([a-z0-9-]+)\.backblazeb2\.com$", endpoint)
    return match.group(1) if match else ("auto" if "r2.cloudflarestorage.com" in endpoint else "")


def space_host(space: str) -> str:
    # <owner>/<name> -> https://<owner>-<name>.hf.space
    owner, name = space.split("/", 1)
    slug = re.sub(r"[^a-z0-9-]", "-", f"{owner}-{name}".lower())
    return f"https://{slug}.hf.space"


def container_secrets(values: dict[str, str]) -> dict[str, str]:
    """Everything the Space needs, keyed exactly as the container reads it."""
    neon = values["NEON_URL"]
    out = {
        "DATABASE_URL_OWNER": owner_url_asyncpg(neon),
        "DATABASE_URL": app_url_asyncpg(neon, values["APP_DB_PASSWORD"]),
        "APP_DB_PASSWORD": values["APP_DB_PASSWORD"],
        "LITELLM_MASTER_KEY": values["LITELLM_MASTER_KEY"],
        "LITELLM_BASE_URL": "http://127.0.0.1:4000",
        "LLM_MAX_CONCURRENCY": "4",
        "MINIO_ENDPOINT": values["B2_ENDPOINT"],
        "MINIO_ACCESS_KEY": values["B2_KEY_ID"],
        "MINIO_SECRET_KEY": values["B2_APP_KEY"],
        "MINIO_SECURE": "true",
        "MINIO_REGION": b2_region(values["B2_ENDPOINT"]),
        "MINIO_BUCKET_RAW": values.get("B2_BUCKET") or "bidproof-tenders-raw",
        # The public origin; deploy_vm.py overrides this with the VM's name.
        "CORS_ORIGINS": space_host(values["HF_SPACE"]) if values.get("HF_SPACE") else "",
        "SCOUT_ENABLED": "false",
        "CONDUCTOR_ENABLED": "true",
    }
    for key in LLM_KEYS:
        out[key] = values[key]
    if values.get("LANGFUSE_PUBLIC_KEY") and values.get("LANGFUSE_SECRET_KEY"):
        out["LANGFUSE_PUBLIC_KEY"] = values["LANGFUSE_PUBLIC_KEY"]
        out["LANGFUSE_SECRET_KEY"] = values["LANGFUSE_SECRET_KEY"]
        out["LANGFUSE_HOST"] = values.get("LANGFUSE_HOST") or "https://cloud.langfuse.com"
    return out
