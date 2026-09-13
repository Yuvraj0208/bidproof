"""Deploy the committed tree to the Hugging Face Space. One command:

    python infra/deploy/deploy_space.py

  1. creates the Space if it does not exist (Docker SDK, private, free CPU)
  2. sets every secret the container reads (derived from .env.deploy + .env)
  3. uploads the files git tracks at HEAD — nothing untracked ever leaves
     this machine — and removes files the Space still has from earlier
  4. waits for the build, then checks /health and /health/models

Reads .env.deploy. Uses the API venv (huggingface_hub comes with Docling).
"""

from __future__ import annotations

import io
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _env import REPO, container_secrets, load_deploy_env, space_host  # noqa: E402

TERMINAL = {"RUNNING", "RUNTIME_ERROR", "BUILD_ERROR", "CONFIG_ERROR", "PAUSED", "STOPPED"}


def tracked_tree(target: Path) -> int:
    """Unpack `git archive HEAD` into target; returns the file count."""
    archive = subprocess.run(
        ["git", "-C", str(REPO), "archive", "--format=tar", "HEAD"],
        check=True, capture_output=True,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        members = [m for m in tar.getmembers() if m.isfile()]
        tar.extractall(target, members=members, filter="data")
    return len(members)


def main() -> int:
    from huggingface_hub import HfApi
    from huggingface_hub.utils import RepositoryNotFoundError

    values = load_deploy_env()
    space = values["HF_SPACE"]
    api = HfApi(token=values["HF_TOKEN"])
    who = api.whoami()["name"]
    print(f"[1/4] Space {space} (as {who})")
    try:
        info = api.space_info(space)
        print(f"      exists · {info.sdk} · private={info.private}")
    except RepositoryNotFoundError:
        api.create_repo(space, repo_type="space", space_sdk="docker", private=True)
        print("      created · docker · private")

    print("[2/4] secrets")
    wanted = container_secrets(values)
    for key, value in wanted.items():
        api.add_space_secret(space, key, value)
    print(f"      {len(wanted)} set")

    print("[3/4] upload the committed tree")
    head = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    with tempfile.TemporaryDirectory() as tmp:
        count = tracked_tree(Path(tmp))
        api.upload_folder(
            repo_id=space,
            repo_type="space",
            folder_path=tmp,
            commit_message=f"deploy {head}",
            delete_patterns=["*"],
        )
    print(f"      {count} files at {head}")

    print("[4/4] build")
    started = time.time()
    stage = None
    while True:
        runtime = api.get_space_runtime(space)
        if runtime.stage != stage:
            stage = runtime.stage
            print(f"      {stage:14} {int(time.time() - started):>4}s")
        if stage in TERMINAL:
            break
        time.sleep(20)
    if stage != "RUNNING":
        print("build did not reach RUNNING; last build log lines:", file=sys.stderr)
        try:
            lines = list(api.fetch_space_logs(space, "build"))
            for entry in lines[-40:]:
                print("   ", entry.get("data", entry))
        except Exception as exc:  # the log stream is best-effort
            print(f"    (could not fetch logs: {exc})")
        return 1

    host = space_host(space)
    print(f"\nrunning at {host}")
    import httpx

    headers = {"Authorization": f"Bearer {values['HF_TOKEN']}"}
    with httpx.Client(headers=headers, timeout=60, follow_redirects=True) as client:
        for path in ("/health", "/health/models"):
            try:
                response = client.get(host + path)
                print(f"  {path:15} {response.status_code} {response.text[:160]}")
            except httpx.HTTPError as exc:
                print(f"  {path:15} {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
