# Hosting BidProof for free

One container runs the whole product — API, LiteLLM gateway, the full parser
ladder (text layer → OCR → layout) and the built web UI on a single URL. Two
managed services sit beside it, both on permanent free tiers:

| Piece | Where | Free tier | Why this one |
|---|---|---|---|
| Container (API + gateway + UI) | **Hugging Face Spaces**, Docker SDK | 2 vCPU, 16 GB RAM, no card | The only free host with enough RAM for Docling + OCR. Sleeps after 48 h idle; wakes on the next visit. |
| Postgres + pgvector | **Neon** | 0.5 GB, no card | The database is 91 MB today. Roles can be created by SQL, so RLS works unchanged. |
| Raw PDFs (S3 API) | **Backblaze B2** (or Cloudflare R2) | 10 GB, no card (R2: 10 GB, card on file) | Same `Minio` client as the compose MinIO — endpoint and keys change, code does not. |
| Tracing (optional) | **Langfuse Cloud** | 50k observations/month | Leave the keys empty and tracing is simply off. |

Model calls still go through OpenRouter with the existing keys. Everything
below is done once; after that one command redeploys.

The same `Dockerfile` runs on Render, Koyeb or a VM — only the RAM differs.
Render/Koyeb free tiers are 512 MB, which fits the API without the ML extra:
build with `--build-arg WITH_ML=0`, and scanned pages are flagged for a human
instead of OCR'd.

---

## What a person does (three sign-ups, no card)

1. **neon.tech** — create a project (Postgres 16, region Singapore). Open
   *Connect*, switch connection pooling **off**, copy the URL.
2. **backblaze.com** — *Buckets → Create a Bucket*: `bidproof-tenders-raw`,
   private. Note the endpoint on the bucket page
   (`s3.us-east-005.backblazeb2.com`). *Application Keys → Add a New
   Application Key*: restrict to that bucket, read and write; copy `keyID`
   and `applicationKey` (shown once).
3. **huggingface.co** — *Settings → Access Tokens → New token*, type
   **Write**. Nothing else; the Space is created by the tool.

Then copy `infra/deploy/env.deploy.example` to `.env.deploy` at the repo root
(gitignored) and fill in those six values. The model keys are taken from
`.env` as they are.

## What the tools do

```bash
apps/api/.venv/Scripts/python.exe infra/deploy/copy_local_data.py
```

Creates the `vector` extension and the `bidproof_app` role in Neon, copies
schema + data from the compose Postgres (`pg_dump | psql`, 91 MB), and mirrors
the PDFs from the local MinIO to B2 (`mc mirror`, 129 MB). Safe to re-run.

```bash
apps/api/.venv/Scripts/python.exe infra/deploy/deploy_space.py
```

Creates the Space (Docker SDK, **private**, free CPU) if needed, sets every
secret the container reads, uploads the files git tracks at `HEAD`, waits for
the build (about 15 minutes the first time: CPU torch, Docling and its models
are baked in so a restart is fast) and then calls `/health` and
`/health/models`. Re-run it to redeploy after a commit.

The Space page shows the same build and run logs; the container prints
`[start] preparing database`, `[start] gateway on 127.0.0.1:4000`,
`[start] api on 0.0.0.0:7860` when it is up.

Optional — deploy on every GitHub push instead: add a repository secret
`HF_TOKEN` and a repository variable `HF_SPACE` (`<user>/bidproof`);
`.github/workflows/deploy-space.yml` pushes `main` to the Space.

## Langfuse Cloud (optional)

cloud.langfuse.com → new project → API keys. Put `LANGFUSE_PUBLIC_KEY` and
`LANGFUSE_SECRET_KEY` in `.env.deploy` and run `deploy_space.py` again. The
Agent Console does not need Langfuse — it reads `agent_runs` from Postgres —
so this only adds the trace view.

---

## Who can reach it

There is no login yet (US-16). Anyone who has the URL can upload a tender and
spend the OpenRouter credit. Two free protections; use both:

* Keep the Space **private**: only the owning Hugging Face account, and
  collaborators added to the Space, can open it.
* On openrouter.ai → Keys, set a **spend limit** on the key the Space uses.

## Checks after the first boot

* `https://<space>/health` → `{"status":"ok","db":"ok"}`
* `https://<space>/health/models` → the three roles `live`
* Upload a tender on the Radar screen and watch the Space log for the parse.

## If something is wrong

| Symptom | Cause | Fix |
|---|---|---|
| Space log: `bootstrap: DATABASE_URL_OWNER is not set` | secret missing | add it, restart |
| `password authentication failed for user "bidproof_app"` | `APP_DB_PASSWORD` differs from the password inside `DATABASE_URL` | make them the same; the boot re-syncs the role |
| `/health/models` shows `deterministic` | gateway not up yet, or `LLM_*` secrets missing | wait 60 s (the health cache) and check the secrets |
| upload fails with an S3 error | wrong endpoint/region, or the key is not allowed on the bucket | check `MINIO_ENDPOINT`, `MINIO_REGION`, key scope |
| Space stays on "Building" | first build downloads about 2 GB | normal; about 15 minutes |
