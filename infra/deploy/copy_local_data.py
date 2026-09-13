"""Copy the local pilot data to the hosted services. Run once, before the
first deploy; safe to run again (inserts are replaced, files are mirrored).

  1. Neon: the vector extension and the bidproof_app role (bootstrap_db.py),
     then schema + data from the compose Postgres via pg_dump | psql.
  2. B2: every object in the local MinIO bucket, via mc mirror.

Reads .env.deploy. Needs Docker running with the compose stack up.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _env import REPO, container_secrets, load_deploy_env  # noqa: E402

PG_CONTAINER = "bidproof-postgres-1"
COMPOSE_NETWORK = "bidproof_default"
VENV_PYTHON = REPO / "apps" / "api" / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def run(cmd: list[str], **kw) -> None:
    print("  $", " ".join(c if len(c) < 60 else c[:20] + "…" for c in cmd))
    subprocess.run(cmd, check=True, **kw)


def main() -> int:
    values = load_deploy_env()
    derived = container_secrets(values)

    print("[1/3] Neon: extension, app role")
    env = {
        **os.environ,
        "DATABASE_URL_OWNER": derived["DATABASE_URL_OWNER"],
        "APP_DB_PASSWORD": derived["APP_DB_PASSWORD"],
    }
    run([str(VENV_PYTHON), str(Path(__file__).with_name("bootstrap_db.py"))], env=env)

    print("[2/3] Neon: schema + data from the local Postgres")
    dump = subprocess.Popen(
        [
            "docker", "exec", PG_CONTAINER,
            "pg_dump", "-U", "bidproof_owner", "-d", "bidproof",
            "--no-owner", "--clean", "--if-exists",
        ],
        stdout=subprocess.PIPE,
    )
    # psql from the official image so nothing needs installing here. The URL
    # is passed as an argument to psql inside the container, never echoed.
    load = subprocess.run(
        [
            "docker", "run", "--rm", "-i", "postgres:16",
            "psql", "--quiet", "-v", "ON_ERROR_STOP=0", values["NEON_URL"],
        ],
        stdin=dump.stdout,
        capture_output=True,
        text=True,
    )
    dump.stdout.close()
    if dump.wait() != 0:
        print("pg_dump failed", file=sys.stderr)
        return 1
    errors = [
        line for line in load.stderr.splitlines()
        if "ERROR" in line and "does not exist, skipping" not in line
    ]
    for line in errors[:20]:
        print("   ", line)
    if load.returncode != 0 or errors:
        print(f"psql reported {len(errors)} error line(s); see above", file=sys.stderr)
        if load.returncode != 0:
            return 1

    print("[3/3] B2: mirror the PDFs")
    endpoint = "https://" + values["B2_ENDPOINT"].removeprefix("https://")
    bucket = derived["MINIO_BUCKET_RAW"]
    script = (
        "mc alias set local http://minio:9000 "
        f"{os.environ.get('MINIO_ROOT_USER', 'bidproof')} "
        f"{os.environ.get('MINIO_ROOT_PASSWORD', 'bidproof_dev_minio')} >/dev/null && "
        f"mc alias set remote {endpoint} {values['B2_KEY_ID']} {values['B2_APP_KEY']} >/dev/null && "
        f"mc mirror --overwrite --quiet local/tenders-raw remote/{bucket} && "
        f"echo objects: $(mc ls --recursive remote/{bucket} | wc -l)"
    )
    subprocess.run(
        ["docker", "run", "--rm", "--network", COMPOSE_NETWORK, "--entrypoint", "sh",
         "minio/mc", "-c", script],
        check=True,
    )
    print("\ndata copied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
