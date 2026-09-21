# Hosting BidProof for free

One container runs the whole product — API, LiteLLM gateway, the full parser
ladder (text layer → OCR → layout) and the built web UI on a single URL. Two
managed services sit beside it, all on permanent free tiers:

| Piece | Where | Free tier | Why this one |
|---|---|---|---|
| Container (API + gateway + UI) | **Oracle Cloud Always Free** VM, behind Caddy | 4 ARM cores, 24 GB RAM, forever; card for identity check only | The only free compute with room for Docling + OCR. Always on, no sleeping. |
| Postgres + pgvector | **Neon** | 0.5 GB, no card | The database is 91 MB today. Roles can be created by SQL, so RLS works unchanged. |
| Raw PDFs (S3 API) | **Backblaze B2** | 10 GB, no card | Same `Minio` client as the compose MinIO — endpoint and keys change, code does not. |
| HTTPS + login | **Caddy** on the VM | — | Let's Encrypt certificate on `bidproof.<ip>.sslip.io`; one shared user/password in front of everything until US-16. |
| Tracing (optional) | **Langfuse Cloud** | 50k observations/month | Leave the keys empty and tracing is simply off. |

Model calls still go through OpenRouter with the existing keys. Everything
below is done once; after that one command redeploys.

Hugging Face Spaces was the first choice (16 GB free) but Docker Spaces now
need a PRO subscription; `deploy_space.py` is kept for anyone who has one.
The same `Dockerfile` also runs on Render or Koyeb free tiers (512 MB) with
`--build-arg WITH_ML=0`: no OCR — scanned pages are flagged for a human — and
a slow CPU.

---

## What a person does (three sign-ups)

1. **neon.tech** — create a project (Postgres 16, region Singapore). Open
   *Connect*, switch connection pooling **off**, copy the URL.
2. **backblaze.com** — *Buckets → Create a Bucket*: `bidproof-tenders-raw`,
   private. Note the endpoint on the bucket page
   (`s3.us-east-005.backblazeb2.com`). *Application Keys → Add a New
   Application Key*: restrict to that bucket, read and write; copy `keyID`
   and `applicationKey` (shown once).
3. **oracle.com/cloud/free** — sign up (home region: one with free ARM
   capacity, e.g. India South · Hyderabad). *Compute → Instances → Create*:
   Ubuntu 24.04 aarch64, shape **VM.Standard.A1.Flex**, 4 OCPU / 24 GB,
   public IPv4, *generate a key pair* and save the private key. On the
   instance's subnet, *Default Security List → Add Ingress Rules* for TCP
   80 and 443 from `0.0.0.0/0`. "Out of host capacity" means retry later.

Then copy `infra/deploy/env.deploy.example` to `.env.deploy` at the repo root
(gitignored) and fill in the Neon URL, the B2 endpoint and key, and the VM's
public IP and key path. The model keys are taken from `.env` as they are.

## What the tools do

```bash
apps/api/.venv/Scripts/python.exe infra/deploy/copy_local_data.py
```

Creates the `vector` extension and the `bidproof_app` role in Neon, copies
schema + data from the compose Postgres (`pg_dump | psql`, 91 MB), and mirrors
the PDFs from the local MinIO to B2 (`mc mirror`, 129 MB). Safe to re-run.

```bash
apps/api/.venv/Scripts/python.exe infra/deploy/deploy_vm.py
```

Over SSH: opens ports 80/443 in the VM's host firewall and installs Docker
(`vm_setup.sh`, once), copies the files git tracks at `HEAD` to
`/opt/bidproof/src`, writes the container's environment and the site login,
builds the image **on the VM** (ARM wheels, 15–25 minutes the first time) and
starts it behind Caddy (`compose.vm.yml`), then waits for
`https://bidproof.<ip>.sslip.io/health`. Re-run it to redeploy after a commit.
`SITE_USER` / `SITE_PASSWORD` in `.env.deploy` are the login it prints.

The VM keeps the full build log at `/opt/bidproof/build.log`; the running
services answer to
`docker compose -f /opt/bidproof/src/infra/deploy/compose.vm.yml logs`.

```bash
apps/api/.venv/Scripts/python.exe infra/deploy/deploy_render.py
```

The no-card fallback while free ARM capacity is unavailable. Needs
`RENDER_API_KEY` in `.env.deploy`, Render's GitHub app allowed on the repo,
and `main` pushed. Creates a free Docker web service in Singapore built with
`WITH_ML=0` (the 512 MB instance has no room for Docling: text-layer PDFs
parse normally, scanned pages are flagged for a human), sets the environment,
waits for the deploy and checks `/health`. Free services sleep after 15 idle
minutes and take about a minute to wake. There is no site login on this path
— the URL is unlisted, not protected — so keep a spend limit on the OpenRouter
key.

## Langfuse Cloud (optional)

cloud.langfuse.com → new project → API keys. Put `LANGFUSE_PUBLIC_KEY` and
`LANGFUSE_SECRET_KEY` in `.env.deploy` and run the deploy again. The
Agent Console does not need Langfuse — it reads `agent_runs` from Postgres —
so this only adds the trace view.

---

## Who can reach it

There is no login in the product yet (US-16). Caddy asks for the shared
`SITE_USER` / `SITE_PASSWORD` before serving anything — the UI, the API, the
PDFs — so the OpenRouter credit is not open to the internet. Share that login
with reviewers; change `SITE_PASSWORD` in `.env.deploy` and redeploy to
rotate it. Setting a **spend limit** on the OpenRouter key is still wise.

## Checks after the first boot

* `https://bidproof.<ip>.sslip.io/health` → `{"status":"ok","db":"ok"}`
* `https://bidproof.<ip>.sslip.io/health/models` → the three roles `live`
* Upload a tender on the Radar screen and watch `docker compose logs -f app` for the parse.

## If something is wrong

| Symptom | Cause | Fix |
|---|---|---|
| app log: `bootstrap: DATABASE_URL_OWNER is not set` | `.env.deploy` incomplete | fill it, redeploy |
| `password authentication failed for user "bidproof_app"` | `APP_DB_PASSWORD` differs from the password inside `DATABASE_URL` | make them the same; the boot re-syncs the role |
| `/health/models` shows `deterministic` | `LLM_*` keys missing from `.env` | fix `.env`, redeploy |
| upload fails with an S3 error | wrong endpoint/region, or the key is not allowed on the bucket | check `MINIO_ENDPOINT`, `MINIO_REGION`, key scope |
| browser shows a certificate error | Caddy is still obtaining the certificate | wait a minute and reload |
| "Out of host capacity" when creating the VM | free ARM shapes are popular | retry in 10–15 minutes; it clears |
