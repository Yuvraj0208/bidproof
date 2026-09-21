"""Deploy to a Render free web service. One command:

    python infra/deploy/deploy_render.py

  1. finds or creates the service: Docker, plan free, Singapore, built from
     the GitHub repo's main branch with WITH_ML=0 (512 MB has no room for
     Docling — scanned pages are flagged for a human, text PDFs work)
  2. sets every environment variable the container reads
  3. waits for the deploy, then checks /health and /health/models

Reads .env.deploy: RENDER_API_KEY plus the Neon/B2 values; the model keys come
from .env. The repo URL is taken from `git remote get-url origin`, so the
branch must be pushed first — Render clones it.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _env import REPO, container_secrets, load_deploy_env  # noqa: E402

API = "https://api.render.com/v1"
NAME = "bidproof"
REGION = "singapore"
DONE = {"live"}
FAILED = {"build_failed", "update_failed", "canceled", "pre_deploy_failed", "deactivated"}


def repo_url() -> str:
    url = subprocess.run(
        ["git", "-C", str(REPO), "remote", "get-url", "origin"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return url.removesuffix(".git")


def main() -> int:
    values = load_deploy_env()
    key = values.get("RENDER_API_KEY")
    if not key:
        raise SystemExit(".env.deploy is missing RENDER_API_KEY")
    client = httpx.Client(
        base_url=API, headers={"Authorization": f"Bearer {key}"}, timeout=60,
    )

    owners = client.get("/owners", params={"limit": 20}).raise_for_status().json()
    owner = next((o["owner"] for o in owners if o["owner"]["type"] == "user"), owners[0]["owner"])
    print(f"[1/3] Render workspace {owner['name']}")

    env = container_secrets(values)
    # Same origin: the API serves the UI, so no cross-origin requests exist.
    env["CORS_ORIGINS"] = ""
    # Build-time: Render passes environment variables to the Docker build as
    # build args, which is how the ML extra is left out.
    env["WITH_ML"] = "0"
    env["LLM_MAX_CONCURRENCY"] = "3"
    env_vars = [{"key": k, "value": v} for k, v in env.items()]

    existing = client.get(
        "/services", params={"name": NAME, "type": "web_service", "limit": 5},
    ).raise_for_status().json()
    if existing:
        service = existing[0]["service"]
        print(f"      service exists · {service['serviceDetails']['url']}")
        client.put(f"/services/{service['id']}/env-vars", json=env_vars).raise_for_status()
        deploy = client.post(
            f"/services/{service['id']}/deploys", json={"clearCache": "do_not_clear"},
        ).raise_for_status().json()
        deploy_id = deploy["id"]
    else:
        payload = {
            "type": "web_service",
            "name": NAME,
            "ownerId": owner["id"],
            "repo": repo_url(),
            "branch": "main",
            "autoDeploy": "yes",
            "envVars": env_vars,
            "serviceDetails": {
                "env": "docker",
                "plan": "free",
                "region": REGION,
                "healthCheckPath": "/health",
                "envSpecificDetails": {
                    "dockerfilePath": "./Dockerfile",
                    "dockerContext": ".",
                },
            },
        }
        response = client.post("/services", json=payload)
        if response.status_code >= 400:
            print(response.text[:800], file=sys.stderr)
            if "repo" in response.text.lower():
                print(
                    "\nRender cannot see the repository. In the Render dashboard: "
                    "Account Settings -> Git Providers -> connect GitHub and grant "
                    "access to the bidproof repo, then run this again.",
                    file=sys.stderr,
                )
            return 1
        created = response.json()
        service = created["service"]
        deploy_id = created.get("deployId")
        print(f"      created · {service['serviceDetails']['url']}")

    url = service["serviceDetails"]["url"]
    print("[2/3] build + deploy (about 10 minutes the first time)")
    started = time.time()
    status = None
    while True:
        if deploy_id:
            deploy = client.get(f"/services/{service['id']}/deploys/{deploy_id}").raise_for_status().json()
        else:
            deploy = client.get(f"/services/{service['id']}/deploys", params={"limit": 1}).raise_for_status().json()[0]["deploy"]
            deploy_id = deploy["id"]
        if deploy["status"] != status:
            status = deploy["status"]
            print(f"      {status:22} {int(time.time() - started):>4}s")
        if status in DONE or status in FAILED:
            break
        time.sleep(20)
    if status not in DONE:
        print(f"deploy ended as {status}; open the service's Logs tab in the dashboard", file=sys.stderr)
        return 1

    print("[3/3] health")
    with httpx.Client(timeout=90, follow_redirects=True) as web:
        for path in ("/health", "/health/models"):
            for attempt in range(6):
                try:
                    r = web.get(url + path)
                    print(f"      {path:15} {r.status_code} {r.text[:160]}")
                    break
                except httpx.HTTPError as exc:
                    if attempt == 5:
                        print(f"      {path:15} {exc}")
                    time.sleep(10)
    print(f"\nlive at {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
