# BidProof — demo readiness

Written 2026-07-26, from measurements taken on this machine against the live
system. Every figure here was observed, not estimated. Where something is not
measured it says so rather than guessing — the same rule the product follows.

---

## The Week-3 spine, end to end

| Step | State | Evidence |
|---|---|---|
| **Scrape / upload** | ✅ works | CPPP **10** and GeM **10** real tenders fetched live. Upload accepts a PDF, parses it (Docling + RapidOCR) and triages it. |
| **Sort** | ✅ works | Two lanes plus the Checkpoint-0 queue; each card carries fit %, its match reasons, a countdown and the confidence chip. |
| **Read** | ✅ works | 13 grounded rules on the hard tender, every one with `el_id + page + bbox`. Clause text is now the clause, with the tender's own clause reference and its obligation type. |
| **Matrix** | ✅ works | 19-row table on the shared DataTable: verdict, confidence, our position, page. Filters for family and "needs attention". Excel export opens (verified in openpyxl, 12 columns incl. `Proof (el_id)`). |
| **Go/No-Go in ₹** | ✅ works | EV as the hero figure with the maths term by term (expected profit − bid effort − locked capital). Sign-off gated to Bid Head; override needs a name and a written reason. |
| **Agent Console** | ✅ works | Real numbers, not placeholders: per-agent tokens, **rupee cost**, latency, model role. |

**The spine is demonstrable.** A tender can be scraped or uploaded, read, checked,
decided in rupees, and every claim clicks back to its page and box.

## Confirmed against the SPEC §19 targets

| Target | Measured | Verdict |
|---|---|---|
| Cost per tender under ₹50, shown live | **₹0.037** per decided tender, on screen in Analytics | ✅ comfortably |
| Upload → decision under 10 min | **7.3 min** median (n=1) | ✅ but n is small |
| Hallucination rate zero, by structure | Enforced, not measured: an uncited fact cannot be stored (`el_id` is a NOT NULL FK), and untagged factual sentences are deleted from proposals | ✅ by construction |
| Attack suite 100% every commit | **8/8 passing** | ✅ |
| Eligibility extraction F1 above 0.90 | **NOT MEASURED** on this tenant | ⚠️ Analytics shows `is_this_honest: false` rather than a number |

## What is strong

* **Proof.** Click-to-proof works, the export carries a `Proof (el_id)` column, and the
  ground-check is structural rather than hopeful.
* **The export blocker.** It genuinely refuses (409 + itemised blockers) and the override is
  gated to Bid Head with a mandatory written reason. This demos well.
* **Honest degradation.** The mode badge showed "Templates only — no model credit" during a
  real outage, and Analytics prints "Not calibrated yet" instead of inventing a curve. A
  sponsor cannot be shown a template answer dressed as a model answer.
* **Human control.** Nothing reaches a model until a human presses **Process with AI** on a
  specific tender; the Review tab collects every pending checkpoint in one place.
* **Governance that bites.** Editing a prompt failed CI until the gold set passed and the new
  hash was re-approved. That happened for real during this work, not as a demo script.

## What is weak — say this before the sponsor finds it

1. **The proposal is good, not yet long.** ~7.5k characters over 7 sections, formal register,
   every figure tagged. A real bid response is longer. The writer now has code-computed
   derived facts (average turnover, capacity) which unstuck three sections; the remaining
   gap is depth, not correctness.
2. **Verdict reasons could cite provenance harder.** They state both sides
   ("ships in 30 days vs 90 required") but do not name the company record they came from.
3. **Risk register has no ₹ impact yet.** Risks are raised and counted; the per-clause rupee
   figure is still to do.
4. **Calibration and coverage-vs-accuracy are unmeasured.** Both need the labelled gold set
   scored. The screens say so.
5. **Portal PDFs are not reachable.** CPPP and GeM listings give metadata only — the
   documents sit behind a session. Scraped tenders therefore cannot be read without a manual
   upload, and `/process` returns a 409 that explains exactly this.
6. **One tender, one org of demo data.** TAT and cost medians are n=1.

## Environment warnings for demo day

* **Docker Desktop on this machine is unstable.** Postgres stopped responding several times
  and the daemon hung once. If a screen shows "Could not load", restart
  `bidproof-postgres-1`. `/health` now reports `degraded` instead of pretending to be `ok`.
* **Never run the integration tests before a demo** — they TRUNCATE the database by design.
  Recover with one command:
  `python -m uv run --project apps/api python infra/seed/seed_demo.py`
  It prints the organisation id to paste into the app.
* **Model credit is real money.** The whole build cost about $0.28. Keep a few dollars on the
  account; when it runs dry the app keeps working but serves templates, and the badge says so.
* Start the API with `--reload` so code changes land without a manual restart.

## Suggested demo order

1. **Tender Radar** — press ⟳ Scrape now; real government tenders appear, costing nothing.
2. Upload `infra/seed/fixtures/tender_hard.pdf`, then press **⚡ Process with AI** — this is
   the moment to say that no tender reaches a model without a human choosing it.
3. **Review tab** — "here is everything waiting for a human", numbered by checkpoint.
4. **Matrix** — filter to "Needs attention", click a row, watch the PDF highlight the exact box.
5. **Decision Room** — the EV in rupees, term by term; sign off as Bid Head, and show a
   viewer being refused.
6. **Proposal → Export** — it refuses, itemises why, and demands a name and reason to override.
7. **Agent Console** — what the whole run cost in rupees.
8. **Admin / Analytics** — the audit trail, and the metrics that admit what they cannot yet prove.
