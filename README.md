# BidProof

**Find government tenders, read them, decide if you should bid — in rupees — and draft the proposal. With proof for everything.**

BidProof watches government tender portals, reads the documents (300–800 page PDFs, some scanned, some in Hindi), checks every rule against what your company actually has, tells you whether to bid **as a rupee figure**, and drafts the proposal. A human approves every important step.

Its one defining promise: **every fact, verdict, and sentence clicks back to the exact page and box it came from.** The system is allowed to say *"I don't know."* It is never allowed to guess.

---

## The problem it solves

Companies that sell to the government drown in tenders. A single tender can be an 800‑page PDF — half scanned, price tables printed sideways. A sales engineer spends two days reading one. About **one bid in three is thrown out on paperwork** before the price is even opened. And the biggest loss is invisible: the tenders nobody ever saw.

BidProof turns those two days into a few minutes, and turns "we missed it" into a live list of opportunities.

---

## What it does, step by step

```
   Discover            Read              Check             Decide            Draft
   ────────         ─────────         ─────────         ─────────         ─────────
  Watch portals →  Turn the PDF  →  Match every rule → Bid or no-bid  →  Write the
  + manual         into text you    against what       in RUPEES, with   proposal,
  upload           can trust,       your company       the maths shown   every sentence
                   every line       actually has       term by term      backed by your
                   tied to a                                             real data
                   page + box
```

Every stage leaves a trail you can click:

| Output | What you get |
|---|---|
| **Tender Radar** | Two lists — tenders in your lane, and tenders you could win but never bid on. Each card explains itself. |
| **Compliance Matrix** | Every rule vs your position, with a verdict, a confidence light, and click‑to‑proof. Exports to Excel. |
| **Bid Decision** | Go / No‑Go as a **rupee expected value**, with the formula shown term by term. A named human signs it off. |
| **Amendment Alerts** | When the buyer changes the tender, an alert names exactly what changed, which rules broke, and the new EV. |
| **Pre‑bid Questions** | For every rule you fail, a drafted letter asking the buyer to relax it — citing the clause and page. |
| **Proposal Draft** | A full draft where every factual sentence is tagged to your real company data and fact‑checked. |
| **Agent Console** | A live view of every step — how many tokens, how many rupees, how long. |

---

## Why it's different

1. **Proof, not vibes.** Nothing exists in the system unless it can point at the page and box it came from. This is enforced in the database, not just hoped for — an uncited fact literally cannot be stored. The same mechanism is also the defence against poisoned documents.
2. **Decisions in rupees.** Not a score out of ten — an expected‑value figure a CFO can argue with, with the maths on screen.
3. **Numbers are never done by an AI.** Every turnover check, delivery‑day comparison, and EV calculation is plain, testable code. Models handle language; code handles arithmetic.
4. **The human has the last word.** The bid decision, the proposal sections, and the final submission never auto‑pass.
5. **Safe by design.** A tender PDF is treated as attacker‑controlled input. No agent can send email, submit a bid, export, or delete. Ever.

---

## How it's built

BidProof is a **team of small, single‑job agents** coordinated by one orchestrator. Each agent does exactly one thing, has its own guardrails, and talks to the others only through strict, typed messages.

```
                     ┌─────────────┐
                     │  Conductor  │  runs the team, pauses at
                     └──────┬──────┘  every human checkpoint
        ┌───────┬──────┬────┴────┬────────┬─────────┐
     Scout   Triage  Parser  Extractor  Matcher  RiskScorer
                                            └────┬────┘
                                              Decider  ← bid/no‑bid in ₹
        ┌──────────────┬──────────────┬───────────┴──────────┐
   AmendmentWatcher  QuestionWriter  ProposalWriter → FactChecker
                     FormFiller      Librarian        Guard
```

Every AI call goes through one gateway with three roles — **small / mid / strong** — chosen by config, never hard‑coded. Swapping the underlying model is a one‑line change, not a code change.

### Tech stack

| Layer | Choice |
|---|---|
| Backend | FastAPI (Python), PostgreSQL + pgvector, MinIO (files), Redis |
| Agents | Typed Python packages, one per agent; LiteLLM gateway; Langfuse for tracing |
| PDF / ML | pypdfium2 + Docling + PaddleOCR‑VL (a cheapest‑first reader ladder), BGE‑M3 retrieval |
| Frontend | React + TypeScript + Tailwind, pdf.js for click‑to‑proof |
| Infra | Docker Compose (one command brings up the whole stack) |

Everything is multi‑tenant from day one: each company's data is isolated at the database level with row‑level security.

---

## Getting started

**You need:** Docker Desktop, Python 3.12, Node 20+, and [uv](https://github.com/astral-sh/uv) (`pip install uv`).

**1. Start the infrastructure** (Postgres, MinIO, Redis, tracing, the model gateway):

```bash
cp .env.example .env
docker compose -f infra/docker-compose.yml --env-file .env up -d
```

**2. Set up the database and start the API:**

```bash
uv sync --project apps/api
uv run --project apps/api alembic -c apps/api/alembic.ini upgrade head
uv run --project apps/api uvicorn app.main:app --port 8000
```

The API is now at **http://localhost:8000** — open **/docs** for an interactive view of every endpoint.

**3. Start the web app:**

```bash
cd apps/web
npm install
npm run dev
```

Open **http://localhost:5173**.

**4. Load some demo data** (a sample company and its catalogue):

```bash
uv run --project apps/api python infra/seed/seed_capability_demo.py
uv run --project apps/api python infra/seed/seed_library_demo.py
```

Then upload the sample tender in `tests/fixtures/digital.pdf` and watch it flow through the pipeline.

---

## Turning on the AI models

Out of the box, BidProof runs in a **fully deterministic mode** — it uses pattern matching, plain‑code arithmetic, and templates, so you can run and demo the entire pipeline with **no AI keys and no cost.** Extraction, checking, questions, and proposals all work; the AI simply makes them sharper.

To switch real models on, add keys for the three roles in `.env`. The easiest option is a single [OpenRouter](https://openrouter.ai) key, which gives access to open‑weight models (Qwen, Llama, DeepSeek) and paid ones alike:

```env
LLM_SMALL_MODEL=openai/qwen/qwen3-30b-a3b
LLM_SMALL_API_BASE=https://openrouter.ai/api/v1
LLM_SMALL_API_KEY=sk-your-key-here
# ...same for LLM_MID_* and LLM_STRONG_*
```

Restart the gateway container and the agents start using real models — no code changes. Which model wins each role is decided by measuring them on your own labelled data (the Model Lab), not by guesswork.

---

## Project layout

```
apps/api        The API service and the orchestration
apps/web        The React web app
agents/         One folder per agent, each with a one‑page manifest
adapters/       Isolated portal connectors (one site breaking can't break the rest)
infra/          Docker Compose, database migrations, seed data
tests/          Automated tests + the labelled "gold set" for measuring accuracy
docs/           The full specification (the single source of truth)
```

---

## What's working today

The engine is built end to end. You can, right now:

- Upload a tender and watch it parse into grounded, clickable elements
- Discover live tenders from the CPPP government portal
- See the two‑list Tender Radar with fit scores
- Get a compliance matrix with verdicts, confidence, and click‑to‑proof, exportable to Excel
- Get a Go/No‑Go decision in rupees with the maths shown, and sign it off
- Apply a corrigendum and see exactly what changed and how the EV moved
- Draft pre‑bid query letters and a full, fact‑checked proposal
- Watch the whole run — tokens, rupees, time — in the Agent Console

Everything above is covered by an automated test suite (180+ tests) that runs on every change, plus a licence scan that keeps the codebase clean.

---

## Testing

```bash
# fast unit tests
uv run --project apps/api pytest -m "not integration" -q

# everything (needs the Docker stack running)
uv run --project apps/api pytest -q

# web tests
cd apps/web && npx vitest run
```

---

*Built by Yuvraj. Design partner and first customer: Godrej Enterprises Group.*
