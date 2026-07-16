"""Structural guarantees: compose services exist, the gateway knows only the
three roles configured from env, and no vendor or model name ever appears in
application code (CLAUDE.md golden rule 7)."""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_SERVICES = {
    "postgres",
    "minio",
    "redis",
    "clickhouse",
    "langfuse-web",
    "langfuse-worker",
    "litellm",
}

ROLES = {"small", "mid", "strong"}

# Vendor / model fingerprints that must never appear in application source.
# Vendors are configuration: they live in .env only.
FORBIDDEN = [
    "openai",
    "anthropic",
    "claude",
    "gpt-",
    "gemini",
    "qwen",
    "llama",
    "deepseek",
    "mistral",
    "cohere",
    "groq",
    "openrouter",
    "together_ai",
    "together.ai",
    "togethercomputer",
    "fireworks",
    "bedrock",
    "vertex_ai",
    "azure",
]

SCAN_DIRS = ["apps", "agents", "adapters"]
SCAN_SUFFIXES = {".py", ".yaml", ".yml", ".toml"}
SKIP_PARTS = {".venv", "node_modules", "__pycache__", ".pytest_cache"}


def test_compose_defines_required_services():
    compose_path = REPO_ROOT / "infra" / "docker-compose.yml"
    assert compose_path.exists(), "infra/docker-compose.yml is missing"
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    services = set(compose.get("services", {}))
    missing = REQUIRED_SERVICES - services
    assert not missing, f"compose is missing services: {sorted(missing)}"


def test_litellm_config_roles_env_only():
    config_path = REPO_ROOT / "infra" / "litellm" / "config.yaml"
    assert config_path.exists(), "infra/litellm/config.yaml is missing"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    entries = {m["model_name"]: m["litellm_params"] for m in config["model_list"]}
    assert set(entries) == ROLES, (
        f"gateway must expose exactly the roles {sorted(ROLES)}, got {sorted(entries)}"
    )
    for role, params in entries.items():
        for key in ("model", "api_base", "api_key"):
            value = str(params.get(key, ""))
            assert value.startswith("os.environ/"), (
                f"role '{role}' param '{key}' must be an os.environ/ reference, "
                f"got: {value!r}"
            )


def test_litellm_config_contains_no_vendor_literal():
    text = (REPO_ROOT / "infra" / "litellm" / "config.yaml").read_text(
        encoding="utf-8"
    ).lower()
    hits = [word for word in FORBIDDEN if word in text]
    assert not hits, f"vendor literals in gateway config: {hits}"


def test_no_hardcoded_vendor_in_source():
    offenders: list[str] = []
    for scan_dir in SCAN_DIRS:
        base = REPO_ROOT / scan_dir
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.suffix not in SCAN_SUFFIXES:
                continue
            if SKIP_PARTS & set(path.parts):
                continue
            content = path.read_text(encoding="utf-8", errors="ignore").lower()
            for word in FORBIDDEN:
                if word in content:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {word!r}")
    assert not offenders, (
        "vendor/model names belong in .env, never in source:\n" + "\n".join(offenders)
    )
