"""Deploy the committed tree to a VM over SSH. One command:

    python infra/deploy/deploy_vm.py

  1. prepares the VM once (host firewall, Docker) — vm_setup.sh
  2. copies the files git tracks at HEAD to /opt/bidproof/src, and writes
     app.env / caddy.env from .env.deploy (+ the model keys in .env)
  3. docker compose up -d --build — the image is built on the VM itself,
     so an ARM box gets ARM wheels without any cross-building here
  4. waits for https://<SITE_HOST>/health through Caddy's HTTPS

Reads .env.deploy: VM_HOST, VM_SSH_KEY, VM_USER (default ubuntu), plus the
Neon/B2 values. SITE_USER / SITE_PASSWORD are generated on first run and
written back, like the other generated secrets.
"""

from __future__ import annotations

import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _env import DEPLOY_ENV, REPO, container_secrets, load_deploy_env, read_env  # noqa: E402

REMOTE = "/opt/bidproof"
HERE = Path(__file__).resolve().parent


def persist(values: dict[str, str], **fresh: str) -> dict[str, str]:
    text = DEPLOY_ENV.read_text(encoding="utf-8")
    for key, value in fresh.items():
        pattern = re.compile(rf"^{key}=.*$", re.MULTILINE)
        text = pattern.sub(f"{key}={value}", text) if pattern.search(text) else text + f"\n{key}={value}\n"
    DEPLOY_ENV.write_text(text, encoding="utf-8")
    return {**values, **fresh}


def site_host(ip: str) -> str:
    # sslip.io resolves <name>.<a-b-c-d>.sslip.io to a.b.c.d — a real DNS name
    # for a bare IP, which is what Let's Encrypt needs.
    return f"bidproof.{ip.replace('.', '-')}.sslip.io"


class Ssh:
    def __init__(self, host: str, user: str, key: Path) -> None:
        # A private copy with owner-only permissions: OpenSSH refuses a key
        # other users could read, and a file in Downloads usually is.
        self.key = Path.home() / ".ssh" / "bidproof_vm.key"
        self.key.parent.mkdir(exist_ok=True)
        shutil.copyfile(key, self.key)
        os.chmod(self.key, stat.S_IRUSR | stat.S_IWUSR)
        if os.name == "nt":
            # Windows: os.chmod only flips read-only. Git's ssh checks the
            # POSIX mode its own chmod sets; Windows' ssh checks the ACL.
            if shutil.which("chmod"):
                subprocess.run(["chmod", "600", str(self.key)], check=False)
            subprocess.run(
                ["icacls", str(self.key), "/inheritance:r", "/grant:r",
                 f"{os.environ.get('USERNAME', '')}:R"],
                check=False, capture_output=True,
            )
        self.target = f"{user}@{host}"

    def _base(self) -> list[str]:
        return [
            "ssh", "-i", str(self.key),
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "ServerAliveInterval=30",
            "-o", "BatchMode=yes",
            self.target,
        ]

    def run(self, command: str, *, input: bytes | None = None, quiet: bool = False) -> str:
        result = subprocess.run(
            self._base() + [command], input=input, capture_output=True,
        )
        out = result.stdout.decode("utf-8", "replace")
        if result.returncode != 0:
            raise SystemExit(
                f"remote command failed ({result.returncode}): {command[:80]}\n"
                f"{result.stderr.decode('utf-8', 'replace')[-2000:]}"
            )
        if not quiet and out.strip():
            print("      " + out.strip().replace("\n", "\n      "))
        return out

    def stream(self, command: str) -> None:
        """Run with live output — for the long image build."""
        result = subprocess.run(self._base() + [command])
        if result.returncode != 0:
            raise SystemExit(f"remote command failed ({result.returncode}): {command[:80]}")


def main() -> int:
    values = load_deploy_env()
    for key in ("VM_HOST", "VM_SSH_KEY"):
        if not values.get(key):
            raise SystemExit(f".env.deploy is missing {key}")
    if not values.get("SITE_USER") or not values.get("SITE_PASSWORD"):
        values = persist(
            values,
            SITE_USER=values.get("SITE_USER") or "bidproof",
            SITE_PASSWORD=values.get("SITE_PASSWORD") or secrets.token_urlsafe(12),
        )
    host = values["VM_HOST"]
    site = site_host(host)
    ssh = Ssh(host, values.get("VM_USER") or "ubuntu", Path(values["VM_SSH_KEY"]))

    print(f"[1/4] prepare {host}")
    ssh.run("sh -s", input=(HERE / "vm_setup.sh").read_bytes().replace(b"\r\n", b"\n"))

    print(f"[2/4] copy the committed tree and the environment")
    head = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    archive = subprocess.run(
        ["git", "-C", str(REPO), "-c", "core.autocrlf=false", "archive", "--format=tar", "HEAD"],
        check=True, capture_output=True,
    ).stdout
    ssh.run(
        f"rm -rf {REMOTE}/src && mkdir -p {REMOTE}/src && tar -x -C {REMOTE}/src",
        input=archive, quiet=True,
    )

    app_env = container_secrets(values)
    app_env["CORS_ORIGINS"] = f"https://{site}"
    password_hash = ssh.run(
        "docker run --rm -i caddy:2 caddy hash-password",
        input=values["SITE_PASSWORD"].encode(), quiet=True,
    ).strip()
    caddy_env = {
        "SITE_HOST": site,
        "SITE_USER": values["SITE_USER"],
        "SITE_PASSWORD_HASH": password_hash,
    }
    for name, env in (("app.env", app_env), ("caddy.env", caddy_env)):
        body = "".join(f"{k}={v}\n" for k, v in env.items()).encode()
        ssh.run(f"cat > {REMOTE}/src/infra/deploy/{name} && chmod 600 {REMOTE}/src/infra/deploy/{name}", input=body, quiet=True)
    print(f"      {head} at {REMOTE}/src · site https://{site}")

    print("[3/4] build and start on the VM (the first build takes 15-25 minutes)")
    # The full build log stays on the VM; only its tail is shown here, and
    # the exit code is compose's, not tail's.
    ssh.stream(
        f"cd {REMOTE}/src/infra/deploy && "
        f"docker compose -f compose.vm.yml up -d --build > {REMOTE}/build.log 2>&1; rc=$?; "
        f"grep -v -E 'Downloading|Get:' {REMOTE}/build.log | tail -30; exit $rc"
    )

    print("[4/4] health through HTTPS")
    import httpx

    auth = (values["SITE_USER"], values["SITE_PASSWORD"])
    deadline = time.time() + 300
    last = ""
    while time.time() < deadline:
        try:
            with httpx.Client(auth=auth, timeout=30, follow_redirects=True) as client:
                health = client.get(f"https://{site}/health")
                if health.status_code == 200 and health.json().get("db") == "ok":
                    models = client.get(f"https://{site}/health/models")
                    print(f"      /health         {health.text}")
                    print(f"      /health/models  {models.text[:200]}")
                    break
                last = f"{health.status_code} {health.text[:120]}"
        except httpx.HTTPError as exc:
            last = str(exc)[:120]
        time.sleep(10)
    else:
        print(f"      not healthy after 5 minutes; last: {last}", file=sys.stderr)
        print(f"      logs: ssh -i {ssh.key} {ssh.target} 'cd {REMOTE}/src/infra/deploy && docker compose -f compose.vm.yml logs --tail 100'")
        return 1

    print(f"\nlive at https://{site}")
    print(f"login: {values['SITE_USER']} / (SITE_PASSWORD in .env.deploy)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
