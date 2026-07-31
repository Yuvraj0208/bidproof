# BidProof — finishing status

Progress file for the demo-readiness push. Work the tasks **in order**; tick each item
with a one-line note when its tests pass and it is committed.

Environment note: Docker Desktop on this machine is unstable — if the API 500s with
`ConnectionRefusedError [WinError 1225]`, restart `bidproof-postgres-1` and retry.

**Running integration tests wipes the demo data** (the `owner_conn` fixture TRUNCATEs
`tenders, organizations CASCADE`). After any integration run, re-seed before demoing.
Until Task 6 lands, the manual reseed is:

```bash
python -m uv run --project apps/api python infra/seed/seed_capability_demo.py
python -m uv run --project apps/api python infra/seed/seed_library_demo.py
```
(these need a `demo-org` row to exist first — Task 6 must fold org+profile creation into
one idempotent script, since this bit me three times in one session).

The API must be restarted to pick up Python changes unless started with `--reload`:
`python -m uv run --project apps/api uvicorn app.main:app --port 8000 --reload`

---

## ✅ REQUESTS R0–R3 — DONE (2026-07-25), verified live

**R0. "Clicking a tender does nothing / I get an error" — DIAGNOSED, environment not code.**
`GET /radar` was returning **500 with `asyncpg TimeoutError`** — the Postgres container had
stopped responding (Docker's daemon then hung entirely and needed relaunching). `/health`
still answered 200 because it catches the DB error and reports `db: unreachable`, which is
why the app *looked* alive while every screen failed.
**Both product fixes DONE** (commits `44a7755`, `1b6a3c1`):
  * `Workspace.load()` no longer swallows failures — a failed rules read shows an error card
    naming the likely cause ("restart the Postgres container") with a Retry button.
  * `/health` now returns `status: degraded` when the DB is down, instead of `ok`.

**R1. Delete scraped tenders — DONE.** `DELETE /tenders/{id}`, gated to bid_head+ (403 for
bid_executive), audit row written BEFORE the cascade so it survives. Radar cards carry a
Delete button behind a confirm modal that spells out what is lost.
**Verified live:** deleted a tender from the UI → gone from the list, `tender_deleted by
bid_head` in the audit log.

**R2. Per-tender opt-in before any model call — DONE.** Upload now runs parse + triage only
(both free, both local); the extract/check background tasks were removed. `POST
/tenders/{id}/process` is the ONLY route to a model, gated to bid_executive+ and audited as
`tender_processed_with_ai`. Radar cards carry **⚡ Process with AI**.
**Verified live:** two tenders uploaded → **0 rules each, no model call**; pressing process
on one → 19 rules, 6 gaps. A metadata-only portal tender returns a 409 that explains itself
rather than failing. 4 integration tests lock this in, including
`test_upload_alone_never_reaches_a_model` which asserts the fake gateway saw **no calls**.

**R3. One place per tender for every human decision — DONE.** New **Review** tab, now the
FIRST tab in the workspace, showing a numbered card per outstanding checkpoint (0,2,3,4,5,6)
with what is being asked, how many items, whether it blocks submission, and a button that
jumps to the control. `pendingReviews()` is a pure function over state the workspace already
loads — it adds no requests and cannot disagree with the tabs. 7 tests.
**Verified live:** the hard tender opens on "Review (2)" → checkpoint 3 (7 verdicts) and
checkpoint 6 (5 blockers), both marked blocking; "Open matrix" routes correctly.

---

## ✅ Credit restored (2026-07-25) — spend discipline

Wallet topped up to $5.00. Session spend so far ≈ $0.19 → **$4.81 remaining**. One full
proposal generation (7 `strong` calls) is roughly 2 cents. Rules of thumb adopted:
re-verify offline against stored output wherever possible instead of regenerating, and
never re-run a generation just to look at it again.

### ⚠️ Demo-data gap found while verifying (belongs to Task 6)
Pre-bid letters are drafted **only for rules with a `gap` verdict** (`QUERYABLE_VERDICTS =
{"gap"}`). The demo tender currently produces 6 complies / 6 needs_human / 6 not_applicable
and **zero gaps**, so `POST /questions` correctly returns `{"letters": 0}` — the
QuestionWriter path cannot be demonstrated at all. Task 6's seed **must include a tender
with a genuine failing requirement** (e.g. a certification the company does not hold), or
this part of the spine is invisible in the demo.

---

## ⛔ RESOLVED — was: no model credit

`https://openrouter.ai/api/v1/credits` reports **total_credits 0, total_usage $0.1923 →
balance −$0.19**. Every sizeable model call now returns **402 Payment Required**, so the
whole pipeline silently serves deterministic templates:

```
writer polish failed for cover_letter: Client error '402 Payment Required'
  for url 'http://localhost:4000/v1/chat/completions'   (× all 7 sections)
```

**Nothing in Task 2 that needs a live model can be verified until the account is topped
up** — proposal depth, verdict justifications, risk ₹-impact, formal pre-bid letters, and
the sample outputs all require real calls. Unit-level work continues fine.

Two things were fixed *because* of this:
* the health probe used to ask for only 200 tokens, so it reported **`mode: live` on an
  exhausted balance** while every real generation failed — it now probes with the writer's
  real budget (1600) so the UI cannot show a false green;
* a 402 is now reported as *"no model credit — top up the account behind the gateway"*
  rather than a raw HTTP code.

---

## Audit (Task 1) — completed 2026-07-25

Method: API + web started, real requests against the seeded demo org
`bf7075b9-e55f-4355-a952-c020ae429dbc` and processed tender `5196bd56…`. Exports were
downloaded and opened programmatically. Findings are evidence-based, not inferred.

### What genuinely works (verified, not assumed)

| Area | Evidence |
|---|---|
| Upload → parse → rules → verdicts | 18 rules (12 pattern + 6 AI), 18 verdicts on the demo tender |
| **Excel export** | `GET /matrix.xlsx` → 7,013 bytes, **opens in openpyxl**, 19 rows × 12 cols, headers incl. `Proof (el_id)`, real data |
| **Word export** | `POST /proposal/export` (bid_head override) → 39,054 bytes, **opens in python-docx**, 17 paragraphs + compliance-matrix table (19 rows) |
| **Export blocker** | Correctly refuses with 409 + 6 blockers (unaddressed mandatory clause, contradicted claims). Override correctly gated to `bid_head` (403 for reviewer) |
| **Agent Console** | **Real** numbers: 17 calls, 4,519 tokens, ₹0.2069, real per-agent latency + model roles (`mid`) |
| Discovery / scraping | **Real live portals**: CPPP 10 tenders, GeM 10 tenders (Playwright installed this session) |
| Role gating | Checkpoint 4 gated to bid_head; viewer/reviewer correctly blocked, verified in-browser |
| OCR | RapidOCR wired; `scanned.pdf` → pages_ocr=2, pages_flagged=0, 14 grounded elements |
| Click-to-proof | Rules render with page+bbox; PdfProof highlights (verified in-browser earlier) |

### Defects — must fix

**D1. Prompt scaffolding leaks into the exported proposal.** The Company Profile section
in the exported .docx literally begins `<draft section="company_profile">`. The strong
model echoed the prompt's XML fence into the output and nothing strips it. Visible in a
document we would hand a customer. **Severity: critical (demo-visible).**

**D2. Proposal is far too shallow.** 7 sections, 4,416 characters total (~630 chars per
section). `deterministic_section()` emits 1–4 short lines per section and the "polish"
prompt only restyles them. A real government bid response is many pages. **Severity: critical.**

**D3. Chat is a template, not intelligence.** `_compose_answer()` accepts a `gateway`
argument **and never uses it** — it string-joins matched clauses. Worse, asking the
legitimate question *"What is the EMD for this tender?"* returned the out-of-scope refusal
*"I can only discuss the tenders in this workspace."* with 0 citations — a **false refusal**
on an in-scope question. **Severity: critical (demo-visible).**

**D4. No design system.** No `tailwind.config`, no tokens, no primitives, no `framer-motion`,
no AppShell/sidebar. Two screens (`App.tsx` radar, `Workspace.tsx`) carry ad-hoc utility
classes. Does not meet the Linear/Stripe bar. **Severity: critical (this is Task 4).**

**D5. Missing screens.** SPEC §17 lists ten. **Analytics and Admin do not exist in the web
app at all** — no route, no component. (`admin.py` + `modellab.py` routers exist server-side
with no UI for admin.) **Severity: high.**

**D6. No router / no navigation.** No `react-router`; screens are swapped via `useState`
booleans in `App.tsx`. No sidebar, no deep links, no URL per screen, no back-button support.
**Severity: high.**

**D7. Rule extraction is thin.** Rules carry `key`, `requirement_text`, `value` but no
clause number, no obligation type, and requirement text is often a truncated line rather
than the full rule. **Severity: high (Task 2).**

**D8. Verdict reasons are labels, not justifications.** e.g. `"Medium-duty long-span
shelving"` as the reason for a `complies` verdict — it does not state the tender
requirement vs the company record in a sentence a bid manager would accept. **Severity: high.**

**D9. Mode is invisible.** Nothing in the UI says whether a result came from real models or
the deterministic fallback, and the API does not fail loudly when keys are missing.
**Severity: high (Task 2 requirement).**

**D10. Pre-bid letters are not formal correspondence.** No letterhead structure, no
reference numbers, no formal Indian government register. **Severity: medium.**

**D11. Risk register is shallow.** Risks exist but without per-clause ₹ impact analysis and
"why it matters". On the demo tender: 0 risks surfaced. **Severity: medium.**

**D12. No empty / loading / error states.** Screens render bare text like
"No tenders in this list yet". No skeletons, no toasts, no error surfaces. **Severity: medium.**

**D13. Demo data is thin.** One processed tender; 42 scraped tenders all sitting in
"Needs human" with no worked amendment, no library proposals visible, no multi-stage
pipeline. Screens look empty cold. **Severity: high (Task 6).**

**D14. No `/kitchen-sink` route** for primitives. **Severity: low (Task 4 deliverable).**

### Notes / non-defects
- The docx **does** already attach the compliance matrix and a decision line — better than expected.
- The 409 on export is **correct behaviour** (the export blocker is demo spine), not a bug.
- `GET /proposal → 404` before generation is correct.
- CPPP yields tender **metadata** only (PDFs are session-gated on the portal); that is a
  portal limitation, not a defect.

---

## Task list

### Task 1 — Honest audit
- [x] Walk every screen, produce evidence-based defect list — done above (D1–D14), commit `docs: audit`

### Task 2 — Turn on real intelligence
- [x] **Gateway wiring verified** — `strong` was pointed at a *reasoning* model
      (`deepseek-r1`): it spent its budget in `reasoning_content` and returned empty
      `content`, so the writer silently fell back to templates. **This was the root cause
      of the shallow proposal.** Role repointed to `deepseek-chat` (config change only).
      `/health/models` now probes all three roles; `mode: live` confirmed. Commit `278b5f1`.
- [x] **Loud startup check** — `app/llm/availability.py` probes each role at boot and logs
      `MODEL CHECK: live|DEGRADED|DETERMINISTIC` with the broken roles named. Never raises
      (the API must boot so the UI can *show* the degraded state). Commit `278b5f1`.
- [ ] Mode surfaced **in the UI** — API side done (`GET /health/models`), web badge still to build
- [ ] Rule extraction: full text, clause number, family, obligation type, numeric threshold
- [ ] Verdicts: reasoned justification citing tender element + company record
- [ ] Risk register: per-clause ₹ impact + why it matters
- [ ] Pre-bid letters: formal Indian government correspondence
- [~] **Proposal — much improved, not finished.** Commit `392a5ee`.
      Fixed: **D1 scaffolding leak** (`<draft section=…>` reached an exported .docx —
      now stripped and verified absent), and **model narration** ("Okay, let me start by…")
      which the new `looks_like_reasoning()` guard catches with one strict retry before
      falling back to the grounded draft. `extract_text()` no longer returns
      `reasoning_content` as prose by default.
      Measured on the demo tender: dropped-untagged sentences **126 → 13**, contradicted
      claims **13 → 4**, export verified free of scaffolding *and* narration.
      **Still weak:** 3 of 7 sections (company_profile, eligibility_compliance,
      commercial_terms) still fall back to the short template, so the whole document is
      ~5.4k chars — not yet the "genuinely long" target.
      **Root cause + next step:** the model narrates when a requirement needs a *computed*
      figure (average annual turnover) because prompt rule 4 forbids computing.
      **→ DONE in code, NOT YET VERIFIED END TO END (commit `c69a666`).** `derived_facts()`
      now computes average annual turnover, combined monthly capacity and largest executed
      order in plain Python and appends them as ordinary tagged facts, so the writer has
      the number and stops arguing with itself. Arithmetic stays in code, never the model
      (golden rule 3). 4 new unit tests cover it (average correct, citable/enforceable,
      no average from a single year, capacity summed).
      **Verification is blocked on model credit** (see BLOCKER at the top) — the regenerate
      run produced templates in 1.2 s with 7× `402 Payment Required`.
      One existing assertion changed: `test_fact_context_renders_tagged_lines` asserted
      `len(tagged) == 2`; it now asserts `2 + len(derived_facts(...))`. The count stays
      exact — it was made relational, not loosened.
- [x] **Chat: real reasoning with page citations (D3 fixed).** `_compose_answer()` took a
      `gateway` and never used it. Now calls the `mid` role over the retrieved clauses,
      and **discards any answer that fails a ground-check** (§9 rule 1), falling back to the
      grounded quote. Retrieval gained tender-vocabulary aliases (EMD ↔ earnest money
      deposit) which fixes the **false refusal** on in-scope questions.
      Verified: "What is the EMD?" → *"…Rs 2,50,000, payable at submission (p.1)"* with 2
      citations; "weather in Mumbai" still correctly refused. Commit `278b5f1`.
- [~] Sample output — proposal and verdicts shown to Yuvraj; **pre-bid letter could not be
      shown** because no rule currently fails with `gap` (see the demo-data gap above).

**Proposal after the derived-facts fix (verified live, one generation):**
the three previously-stuck sections came unstuck — company_profile 546→1502 chars,
eligibility_compliance 576→1354, commercial_terms 154→913; total **5,426 → 7,451 chars**,
and four sections now cite the code-computed average turnover. Prose reads as real bid
correspondence ("We confirm our full compliance with the eligibility criteria stipulated
in Tender Notice No. …"), every figure carrying its source tag.

- [x] **FactChecker false contradictions fixed** (commit `d6121fe`). A sentence citing
      several facts — "₹120 cr in FY23 [F:a], ₹135 cr in FY24 [F:b], ₹150 cr in FY25 [F:c]"
      — was checked against only `tags[0]`, so the other two figures were marked
      *contradicted* and **blocked export on a perfectly correct sentence**. Claims are now
      verified against the union of every cited fact; a number in none of them is still
      contradicted, so rigour is unchanged. Re-checked offline against the stored proposal
      (no model spend): **verified 18 → 27, contradicted 13 → 4.**

**Governance note:** changing the writer prompt correctly tripped the prompt-approval CI
gate (SPEC §14). Followed the real flow — ran the gold set (passed), then re-approved the
new hash in `infra/prompt_approvals.json`. The gate was not weakened.

### Task 3 — Fix everything from the audit
- [x] **D7 rule extraction — FIXED** (commit `0de562d`). `requirement_text` was
      `element.text[:500]` — the WHOLE element, which for a parsed page block is the entire
      page, so a rule about the EMD arrived as *"TENDER NOTICE No. 42/2026 Supply of
      industrial storage racks… Earnest"*. Now:
      * `clause_sentence()` narrows it to the clause the match sits in;
      * `clause_ref()` captures the tender's own reference ("Section 1", "Clause 4.2");
      * `obligation_of()` reads must/shall → mandatory, should → recommended, may →
        optional, with **unmarked treated as mandatory** (the safe reading for a tender);
      * restatements are deduped on (key, value) — a tender repeats its terms on every page
        — while the same key with a DIFFERENT value is kept, because that is a real conflict
        a human must see.
      Migration `0020` adds `clause_ref` + `obligation`; both are surfaced on the rule row.
      **Measured on the hard tender: 19 rules → 13, and the text is now
      *"Earnest Money Deposit: Rs 25,00,000 payable at submission."*** 8 new unit tests,
      including one for the bug my first attempt introduced (splitting on ":" stranded the
      figure, leaving just the label "Delivery period:").
- [~] D8 verdict reasons — milder than the audit claimed: reasons already cite both sides
      ("Medium-duty long-span shelving ships in 30 days vs 90 required"). Still worth
      enriching with the company record's provenance.
- [ ] D11 risk register ₹ impact — still to do (needs model calls)
- [x] D12 empty/loading/error states — done as part of Task 4
- [x] D14 kitchen sink — done as part of Task 4

### Task 7 — Final QA (in progress)
- [x] **Attack suite back to 100%** (8/8). My R2 change (upload no longer auto-extracts)
      broke two attack tests that uploaded and went straight to `/check`; they now opt in
      via `/process` exactly as a human does. **The security assertions were not touched** —
      injection still flagged, verdict still decided by arithmetic, poisoned corrigendum
      still cannot flip a verdict.
- [x] Gold set + calibration: 6 passed.
- [x] Unit suites: **154 API + 72 web**.
- [x] **Full integration run: 263 passed, 0 failed** (~21 min).
      The first full run surfaced **15 failures, all caused by my own R2 change**: those
      tests uploaded a tender and went straight to `/check`, which used to work because
      upload auto-extracted. Fixed by inserting the `/extract` step a human now performs —
      20 call sites across 10 files. **No assertion was altered or weakened**; every
      existing expectation about the `/check` response still holds. Commits `f3b9587`
      (attack suite) and `9ad3090` (the other ten files).
      Lesson worth keeping: a deliberate behaviour change ripples through integration
      tests, and the unit suite will not catch it — the full run is not optional.
- [x] Screen walk at **1920×1080 and 2560×1440**: no horizontal overflow at either, 240px
      rail intact, Inter loaded, mode badge reads "Live models".
- [x] **Demo-readiness report** — `docs/DEMO_READINESS.md`. Confirms the Week-3 spine end to
      end and the §19 targets that are genuinely measured (₹0.037/tender vs <₹50; 7.3 min
      upload→decision vs <10; attack suite 8/8; hallucination zero by structure), states
      that **eligibility F1 is NOT measured**, and lists six weaknesses to volunteer before
      the sponsor finds them.

**Demo data restored after the test run** (`seed_demo.py`): org
`2eb0b1ae-c315-4bf5-8be8-409813b9f553` — winnable tender 12 rules / 4 complies, hard tender
13 rules / **4 gaps / 4 pre-bid letters**. Analytics reads it live: 14 DQ risks caught,
₹0.0326 per decided tender.

### Task 4 — The interface
- [x] **Tokens** — `src/index.css` `@theme` (Tailwind v4 is CSS-configured, there is no
      `tailwind.config.js`). Indigo #1E2170 / #2A2D8F / #EDEEFA, ink #1B1D3A, surface
      #F6F7FD, amber #D97706, green #1F8A4C, red #C23A34. Inter self-hosted via
      `@fontsource` (no CDN — the demo box may be offline). Tabular numerals applied to
      every table and `[data-numeric]`. Radius 12 (8/16 relatives), three shadow levels,
      one focus ring that inverts on the indigo rail, `prefers-reduced-motion` respected.
      Verified in-browser: body `rgb(246,247,253)`, ink `rgb(27,29,58)`, rail `rgb(30,33,112)`.
- [x] **AppShell** — dark indigo rail with the wordmark, **all ten SPEC §17 screens**
      (tender-scoped ones disabled until a tender is open), org name pinned at the bottom;
      top bar carries tender context + `CountdownChip` + search + the mode badge.
- [x] **Router** — fixes D6. `react-router-dom`; every screen has a URL, back button works,
      `/workspace/:tenderId` deep-links. Screens were previously swapped with `useState`
      booleans.
- [x] **Mode badge (closes D9's UI half)** — `ModeBadge` polls `/health/models` and shows
      Live / Degraded / Templates-only. Verified live during the credit outage: it reads
      **"◐ Degraded"** with the tooltip *"strong: no model credit — the provider refused the
      request (402 Payment Required). Top up the account…"*. A template answer can no
      longer masquerade as a model answer.
- [x] **Primitives + `/kitchen-sink`** (fixes D14) — Card, PageHeader, Button, StatCallout,
      EmptyState, SkeletonLoader, FieldLabel, DataTable (sticky header, sortable, zebra,
      hover, roving keyboard focus, density toggle), CountdownChip, VerdictBadge, RiskTag,
      Pill, `formatInr` (lakh/crore), Toast, Modal, Tooltip. ConfidenceChip restyled, API
      untouched. **18 new tests** covering countdown thresholds, colour-blind-safety,
      numeric sort, keyboard nav and the empty state.
- [x] **Retrofit — every screen.** Radar (skeletons, teaching empty state, error card with
      retry, countdowns, toasts); **Compliance Matrix rebuilt on DataTable** with family and
      "needs attention" filters, VerdictBadge and per-row proof; **Decision Room** with the EV
      as a hero StatCallout and the risk register on RiskTag (₹ impact); Agent Console totals
      as a hero line; Model Lab, Proposal Studio, Questions, Amendments, Chat, Checklist,
      Onboarding, LearnedNote and PdfProof all migrated. A scripted palette migration moved
      125 legacy Tailwind colours onto the tokens across 9 files, then stragglers were fixed
      by hand. The proof highlight keeps a deliberate warm amber so it pops on white paper.
      Commit `852018c`.
- [x] Loading / empty / error states — on Radar, Matrix, Decision Room, Analytics and Admin.

**Resolved with approval:** the ConfidenceChip dot now uses the tokens (`bg-success` /
`bg-warning` / `bg-danger`); the three matching assertions in `ConfidenceChip.test.tsx` were
updated with the user's go-ahead. Nothing in the UI is off-system any more.

**Two other test hooks preserved rather than edited:** `DataTable` gained an optional
`rowTestId` so the matrix keeps its `matrix-row` hook, and `VerdictBadge` renders the API's
own verdict word (`complies`, not `Complies`) so the screen, the exported .xlsx and the audit
log all say the same thing. Both matrix tests pass untouched.

### Task 5 — Missing screens
- [x] **Analytics** — new `GET /analytics/overview` + screen, reading the same tables the
      pipeline writes so demo and report numbers cannot disagree. Funnel (8 stages), median
      TAT, DQ-risks by family, cost trend per day, confidence bands, and a KPI panel scored
      against the SPEC §19 targets. **Verified live: TAT 7.3 min (target <10), cost ₹0.037
      per tender (target <₹50), 6 DQ risks caught.** Coverage-vs-accuracy, calibration and
      eligibility F1 render an explicit **"Not calibrated yet"** marker (`is_this_honest:
      false`) instead of a fabricated curve. Commit `d0dbd4b`.
- [x] **Admin** — roles, per-role model config (live from `/health/models`), prompt-approval
      governance, thresholds/budgets/kill-switch (marked read-only, since the UI does not
      write them back yet), scraper health from `/discovery/runs`, and the append-only audit
      log on DataTable with a role-aware 403 message. Verified live: it correctly reports
      `strong: no model credit`.

### Task 6 — Real demo data
- [x] **One-command idempotent reset** — `infra/seed/seed_demo.py`, documented in the README.
      Creates the org + radar profile (the piece whose absence broke reseeding three times),
      capability DB, catalogue, library, and two committed tender fixtures which it pushes
      through the real endpoints. `--no-pipeline` seeds without spending anything.
      Also added the missing `if __name__ == "__main__"` guards to the two older seed
      scripts — importing them used to execute them.
- [x] **The failing tender** (`tender_hard.pdf`: ₹500 crore turnover, ISO 45001, 15-day
      delivery). Verified live: **20 rules → 7 gaps, 5 needs_human, 2 complies, 2 risks,
      and 6 pre-bid query letters drafted.** The winnable tender covers the happy path.
      This closes the demo-data gap found earlier — the QuestionWriter half of the spine
      was previously impossible to show.
- [~] Worked amendment example — `corrigendum.pdf` exists as a fixture but the seed does not
      yet apply it; still to wire in.

### Task 7 — Final QA
- [ ] web tests, api tests, gold-set harness, attack suite — all results shown
- [ ] Every screen re-walked; §17 UX principles checked; 1080p + 1440p verified
- [ ] Demo-readiness report (Week-3 spine, what works, what's weak, §19 targets confirmed)

---

## Post-QA defect: real PDFs failed to parse (reported 2026-07-26)

**Symptom.** `6565dbb36c16dTenderdoc144.pdf` uploaded, console showed *parser failed*.
Separately, none of the 18 scraped tenders would open or process.

**Two unrelated causes.**

### 1. One picture destroyed the whole document (real bug, fixed)

`docling_engine.py` read an item's text as:

```python
getattr(item, "text", None) or getattr(item, "export_to_markdown", lambda: "")()
```

Against the installed docling 2.114.0, a `PictureItem` has **no `.text`**, so the `or`
branch ran — and `PictureItem.export_to_markdown(self, doc, ...)` **requires `doc`**,
raising `TypeError: missing 1 required positional argument`. Nothing caught it, so it
propagated out of `ladder.parse()` and `execute_parse_run` marked the entire run
`failed`. **One logo failed an 800-page tender.** Every real government PDF has one.

The fixtures were reportlab text-only, so the whole suite passed while real documents
failed — a coverage gap, not luck. Worse, since the pdfium fallback was chosen at
*wiring* time (is docling importable?) and never on *failure*, having Docling
installed made the product worse than not having it.

Fixed in three places:
- `docling_engine.py` — `item_text()` reads `.text`, else calls `export_to_markdown`
  guarded and with the document; an uncaptioned picture yields `""` and is skipped,
  never invented into an element (§9 rule 1).
- `docling_engine.py` — per-item `try/except`, counted. A malformed item costs one
  element, never the document.
- `ladder.py` — `_extract_text()` falls back to pdfium when the configured extractor
  *raises*. The ladder already degraded honestly for a MISSING engine (SPEC §5.2); it
  now does the same for a FAILING one.

**Regression tests** (`tests/test_parser_ladder.py`, 17 passing): a fixture PDF with an
embedded image; an `ExplodingExtractor` proving the fallback; and three unit tests of
`item_text` including a `PictureLike` that reproduces the exact `TypeError`. Verified by
restoring the buggy line — 2 tests fail; restoring the fix — 17 pass.

### 2. Scraped tenders have no document (correct, but unexplained)

All 18 CPPP/GeM tenders have **no `documents` row**: the portals publish listing
metadata but keep the PDF behind a session. So the workspace showed empty panels and
*Process with AI* returned a 409 the UI only flashed as a toast. Designed behaviour,
never stated.

All 18 do carry a `portal_url`, so the dead end became a next action:
- `has_document` + `portal_url` exposed on both the radar card and tender detail.
- Radar card: no document ⇒ *Process with AI* is replaced by **Open on portal ↗** and
  **↑ Upload its PDF**, with a one-line reason.
- Workspace: a banner explaining it, instead of empty panels; and a separate banner
  when the parse genuinely *failed*, showing the error.

The 409 stays — it is correct. The UI now stops the user reaching it.

### 3. Parse runs that never resolved

The failing document left one `failed` row and one orphaned `running` row, so the
console reported a parse still in flight when nothing was. Two holes, both closed:
- `execute_parse_run` only guarded `ladder.parse`; the block that **persists** pages
  and elements was unguarded, so a storage failure left the row at `running` for ever.
  Both paths now go through `mark_failed`.
- A process killed mid-parse (a `--reload` restart) can never resolve its own row.
  `reap_interrupted_parse_runs()` runs at startup and closes anything left
  `pending`/`running` as failed, with an explicit reason.

### 4. Pages with a perfectly good text layer were being sent to OCR

Found while verifying the fix on the user's own 283-page PDF. Docling hit
`std::bad_alloc` in its preprocess stage and **silently returned a document with
those pages missing** — it did not raise, so the fallback in `_extract_text` never
fired. `looks_like_garbage` then correctly judged the pages empty and routed them to
OCR, at roughly 45 s a page, to re-read text that was already sitting in the file.

Added **step 1b** to the ladder: when a page that step 0 said *has* a text layer comes
back empty or garbled, re-read it with the built-in pdfium reader before escalating to
OCR. A page is only replaced when pdfium returns something that is *not* garbage, so a
genuinely mangled text layer (broken CID fonts) still falls through to OCR — the case
OCR exists for. Cheapest step first is the ladder's whole point (SPEC §5.2).

Measured on the first 6 pages of `6565dbb36c16dTenderdoc144.pdf`:

| | outcome | time |
|---|---|---|
| before any fix | **parse failed entirely** | — |
| picture fix only | 6 pages, 4 of them via OCR | 198 s |
| with step 1b | 6 pages, **all via text layer** | **33 s** |

Extrapolated, the full 283-page document goes from failing outright to roughly 25–30
minutes. Still slow — Docling on CPU is the bottleneck, and that is worth revisiting —
but it now *completes*, and every element carries its page and box.

**Test note.** `test_ladder_reroutes_garbage_text_page_to_ocr` had to change, and it is
worth saying why. It faked a garbage extraction on `digital.pdf`, whose text layer is
actually clean — so under step 1b pdfium correctly recovers it and OCR is never called.
Rather than relax the assertion, the test now runs against a new fixture whose text
layer is *genuinely* unreadable (U+25A0 and friends, 114 chars, so step 0 still routes
it to TEXT). Both original assertions stand unchanged, plus one more. The scenario the
test was written for is now real instead of simulated.

---

## Session 2026-07-26 (b): single operator, bulk delete, portal links, Playwright

### 5. Single-operator mode

Roles are gone from the UI. `getRole()` returns a single constant `admin`, which
outranks every acting floor in the backend, so one person does discovery, review,
sign-off and export with nothing to switch. The pickers are removed from the
landing page and the workspace header; the Admin screen now explains the mode
instead of listing six roles.

**Deliberately NOT removed:** `require_role`, the rank chain, and the audit log.
SPEC §7 checkpoints and the sponsor's explicit ask for checkpoints 2–6 both depend
on the gates existing and recording who approved what. Deleting them to satisfy
"one person" would have traded a governance guarantee for a cosmetic one. There is
simply one operator who satisfies every gate, and re-exposing the picker later is a
frontend change with no backend work. Verified: no `require_role` endpoint is
auditor-only, so `admin` passes all of them.

### 6. Bulk delete

`POST /tenders/bulk-delete` takes up to 200 ids and keeps every guarantee the
single delete has: gated, an audit row per tender written *before* the cascade, and
RLS scoping so ids outside the org are simply never found. Ids that no longer exist
come back in `not_found` rather than failing the batch — a stale tab must not be
able to break the action. Radar gets a select-all bar with an indeterminate state,
per-card checkboxes, and a confirm modal that lists what is about to go.

Also added the Modal's first tests (`apps/web/src/ui/overlays.test.tsx`). It is the
last thing between a click and an irreversible delete and had no coverage.

### 7. "Open on portal" gave "Invalid Url" — the links are tickets, not addresses

Reported with a screenshot. Root cause found by decoding a stored link:

```
/cppp/tendersfullview/<b64>A13h1<b64>A13h1<b64>A13h1<b64>...
  seg0 13984622                          listing id
  seg1 8d6701a30e2a5210cb6a03a36caafa89  hash
  seg3 1785012896                        unix timestamp = 2026-07-25T20:54:56Z
```

Verified live, three ways:
1. GET the stored link → 200, body contains **"Invalid Url.Please Check"**.
2. Scrape a *fresh* link and GET it immediately → **still invalid**.
3. GET the listing page first (so the session cookie `SSESS…` is held), then the
   same link → **resolves**.

So the link is only valid inside the session that minted it. Handing it to the
user's browser could never have worked.

Fix: `app/services/portal_links.py` decides per portal whether a stored
`portal_url` is durable. GeM links are; CPPP deep links are not and are replaced by
the portal's stable search page (`/cppp/tendersearch`) plus a line naming the
reference to search for. Off-portal or IP-literal hrefs are never offered as links
at all — scraped markup does not get to choose where we send the user (SPEC §11.1).

### 8. Playwright for both portals

`bidproof_adapters/browser.py` now holds the shared renderer: lazy import, the
GuardedFetcher allow-list enforced on **every** request the page makes, and
`accept_downloads=False`. GeM uses it because its list is JS-rendered; CPPP uses it
for the session, and falls back to plain HTTP with a logged warning when Playwright
is missing — one adapter degrading, never discovery failing.

### 9. Why scraping documents is hard — and where it is not

The honest answer differs by portal, and it turned out better than expected.

**GeM: documents are fetchable.** `bidplus.gem.gov.in/showbidDocument/<id>` answers
`application/pdf` with `%PDF-` magic, no session, no cookie, no captcha. All 7
scraped GeM tenders already had exactly that URL in `portal_url` — discovery just
never used it, because `parse_bid_cards` never set `pdf_url` and the download
branch in `discovery.py` was therefore dead code. Fixed, plus a new
`POST /tenders/{id}/fetch-document`.

Verified live on two real tenders: `GEM/2026/B/7594220` → 7 pages, and
`GEM/2026/B/7725625` → 13 pages, both `status: succeeded`, Devanagari read
correctly (`बड सं*या/ Bid Number : GEM/2026/B/7725625`).

**CPPP: they are not.** Three separate obstacles, all confirmed:
- detail links are session + timestamp bound, as above;
- the detail page carries **no direct document link** — the only document-ish
  hrefs on it are the portal's own STQC audit certificates;
- documents route through `/cppp/downloaddisp`, a POST form, and the tender page
  references a captcha. Bypassing a captcha is off the table, so this stops here
  and the UI says so plainly.

Fetching is human-triggered, never automatic: discovery still stops at metadata, so
nobody wakes up to hundreds of megabytes of speculative downloads. `document_url()`
is a deliberately narrow gate — known portal host **and** known document path —
so a poisoned listing cannot become an SSRF primitive. It has its own tests,
including lookalike hosts (`gem.gov.in.evil.com`) and scheme games.

### 10. Docling placeholder comments were being stored as tender text

Found while checking the first fetched GeM tender: elements 1 and 2 of page 1 were
`<!-- 🖼️❌ Image not available. Please use PdfPipelineOptions(...) -->`. That is the
*tool* narrating its own limits, and it would have been embedded, retrieved and
quoted as if the tender said it. `item_text` now drops any render that is nothing
but HTML comments, while keeping content that merely contains one. Re-fetch
confirmed: 14,752 elements, **0 placeholders**, first element now
`बड सं*या/ Bid`.

### Verification

- backend `pytest -m "not integration"`: **179 passed**
- frontend `vitest`: **83 passed** (18 files), `tsc --noEmit` clean, build clean
- new tests: 12 portal-link, 4 adapter, 2 bulk-delete (integration), 5 Modal,
  1 Docling-placeholder
- live UI walked: no role switcher, select-all + 16 checkboxes, CPPP cards showing
  "Find on portal ↗" to the search page, GeM cards showing "⬇ Fetch its PDF",
  fetched GeM cards showing "⚡ Process with AI"

**Not verified in-harness:** modal dismissal. The Browser pane does not composite
frames, so framer-motion's exit animation never completes and the node stays
mounted — the *pre-existing* single-delete modal behaves identically there, so it is
the harness, not the code. Covered by the new jsdom tests instead.

---

## Correction: the CPPP "fix" was itself a dead end

Reported with a screenshot: every CPPP tender opened the same page. It did, and the
first fix deserved the complaint — `stable_portal_url` fell back to CPPP's search
form, so eight tenders all landed on one captcha. Functionally that is still broken,
just broken somewhere else.

Digging further found the obstacle is deeper than reported in §7. Checked live
2026-07-26:

| what was tried | result |
|---|---|
| stored deep link | *"Invalid Url.Please Check"* — session + timestamp bound |
| freshly scraped deep link, no session | still invalid |
| fresh link **with** the listing's session cookie | 200, no error banner… |
| …but the page body | **no tender content** — only *"Enter the characters shown in the image"* |
| `/cppp/rss`, `/cppp/rss/latestactivetenders` | 404 — there is no feed |
| `/cppp/resultoftenders`, `/cppp/tendersearchbyproduct` | 404 |

So §7 was half right. It is not only the *documents* that are gated — **CPPP's
tender detail view is captcha-gated too.** The public listing is the entire
captcha-free surface, and a captcha is a deliberate "no automation" sign, which we
do not solve. There is no honest link to a CPPP tender, and no way to read one.

What changed:
- `stable_portal_url` returns **None** for CPPP. It no longer substitutes a search
  page: a control labelled "open the tender" has to open the tender.
- The manual route moved to `portal_search_url` + `requires_captcha`, so the UI can
  warn before sending anyone there. The link now reads
  **"Search manually (captcha) ↗"** and is styled as a secondary action.
- Each CPPP card gains a one-click **copy-the-reference** button, so the manual
  lookup is a paste rather than a hunt.
- The hint says the whole truth: listing only, page and documents both behind a
  captcha, so upload the PDF instead.

Also checked, since it would have been a clean win: only **1 of 8** CPPP rows is
really a GeM bid (`GEM/2026/B/7704484`), so cross-linking CPPP rows to GeM does not
generalise and was not built.

**Open question for Yuvraj:** 8 of 12 radar rows are CPPP and can never be
processed. Worth deciding whether CPPP stays on as a discovery source (useful as a
market signal — titles, references, closing dates) or comes off so the radar only
shows tenders that can actually be worked. Not changed either way without a call.

### Verification (this round)

- backend `pytest -m "not integration"`: **179 passed**; frontend **83 passed**;
  `tsc --noEmit` and build clean
- live radar payload shapes: `cppp|doc=false|canFetch=false|direct=no|search=captcha`
  ×8, `gem|doc=true|direct=YES` ×3, `manual` ×1
- all 3 remaining GeM tenders now carry a real parsed document

---

## Checkpoint 3 asked a question with no answer box

Reported: the Review Hub said *"Decide the verdicts the system would not guess — 10
— blocks submission"*, the matrix showed ten rows badged **queued for human**, and
clicking them did nothing.

It did nothing because there was nothing there. `checks.py` had exactly four
routes — POST /check, GET /verdicts, GET /matrix.xlsx, GET /risks — and
`MatrixTable` had no control of any kind. `needs_human` was a state the product
could enter and never leave. Golden rule 9 ("the human has the last word") was
asserted in the copy and unimplemented in the code, and the export blocker counted
those verdicts, so a tender could be permanently unsubmittable with no route
forward.

**Migration 0021** adds four columns to `verdicts`:

| column | why |
|---|---|
| `system_verdict` | what the checker said, kept forever, so an override stays visible |
| `decided_by` | who settled it |
| `decided_at` | when |
| `decided_reason` | why — required by the API, because an assertion with no reason is not evidence |

`verdict` still holds the *effective* answer, which is what the matrix, the export
blocker and the EV calculation read.

**`POST /tenders/{id}/verdicts/{verdict_id}/decide`** takes `{verdict, reason,
name}`. Design decisions worth stating:

- `needs_human` is **rejected** as an answer (400). It is what is being resolved;
  accepting it would be a way to make the review queue look clear while nothing was
  decided.
- The reason is required (422 on empty). The compliance matrix is the artefact a bid
  is defended with.
- The **first** machine verdict survives a second correction — correcting a
  correction must not erase what the checker actually said.
- The rule's proof (`el_id`, page, bbox) is untouched. The human decides what a
  *cited* requirement means for this company; they never invent the requirement, so
  golden rule 4 still holds.
- Written to the append-only audit log as `verdict_decided_by_human`.

**UI.** Each queued row gets a **Decide →** button (with `stopPropagation`, so it
does not also fire click-to-proof). The form shows the requirement, a *"see it on
page N ↗"* proof link, why it reached a human, the four allowed verdicts, and
required reason + name; Record stays disabled until both are given. A settled row
shows **"you decided · was needs_human"** — a human answer is never dressed up as a
machine one.

### Verification

- Live, on the real tender `GEM/2026/B/7594220` (11 verdicts, 10 queued):
  empty reason → **422**; `needs_human` → **400**; a real decision → **200** with
  `system_verdict: needs_human`, proof chain intact, queue **10 → 9**.
- Through the UI: 9 Decide buttons → filled the form → toast *"Recorded:
  epbg_percentage is partial"*, buttons **9 → 8**, Review Hub count **10 → 8**.
- backend `pytest -m "not integration"`: **179 passed**; frontend **87 passed**
  (4 new matrix tests); `tsc` and build clean.
- 2 new integration tests cover the happy path, both validation refusals, the audit
  row, and the correct-a-correction case.

**Note for Yuvraj:** verifying this recorded two real decisions on
`GEM/2026/B/7594220` — `epbg_duration` → complies and `epbg_percentage` → partial,
both under the name *"setup check"* with a reason saying it was a smoke test.
Re-decide those two with your real answers; re-deciding is supported and keeps the
original machine verdict.


---

## Developer ergonomics: inspect the reader, and run the demo from VS Code

### `tools/inspect_pdf.py`

There was no way to see what the reader ladder actually did to a file. Added a
read-only tool that runs the same `get_ladder()` the API uses, so there is no
second code path to drift:

```
python -m uv run --project apps/api python tools/inspect_pdf.py "<file.pdf>" --pages 1-5 --text
```

Prints which engines are live, the step-0 routing decision per page (character
count → TEXT or OCR), the per-page result (route, status, confidence, elements,
dropped), totals, and sample text with its bounding box. Forces UTF-8 on stdout —
Windows consoles are cp1252 and a government tender is full of Devanagari, so
without it the tool dies on its own output rather than on anything real.

### `.vscode/tasks.json` and `launch.json`

Ctrl+Shift+P → Run Task, or F5 to debug. **DEMO — start everything** is the one to
press before a demo.

**Bug in the first version, reported immediately:** the DEMO task used
`dependsOrder: "sequence"` across all three tasks. A sequence waits for each task
to *finish*, and a dev server never finishes — so it blocked on the API and never
started Vite. Port 8000 came up, 5173 never did.

Fixed by splitting it: infra is one-shot and genuinely completes, so it stays
sequenced first; the two servers moved into a nested task with
`dependsOrder: "parallel"`, which does not wait at all. Both servers also got a
proper `background` problemMatcher (`Application startup complete` for uvicorn,
`ready in` for Vite) so VS Code can tell a running server from a hung task.

## Model probe reported DEGRADED when nothing was wrong

Seen in the same terminal: `MODEL CHECK: DEGRADED … Broken roles: {'mid':
'TimeoutError'}`. Called directly, `mid` answered in 3.3 s.

Measured three rounds through the gateway: `mid` was 0.6 s every time, but
**`small` took 21.7 s once** against a 25 s ceiling, and 2.3 s / 4.2 s the other
times. Hosted providers are erratic under load; any role can trip it.

`probe_roles` now gives a timeout **one retry**, and the ceiling moved 25 s → 45 s.
A 402/401/403 is never retried — those are definitive, and retrying would only
delay honest bad news. The large `max_tokens=1600` budget is unchanged: it is
deliberate, because a small probe still succeeds on an exhausted balance while
every real generation fails.

Re-probed after the change: **mode `live`**, all three roles OK.

### `tools/show_company.py`

"What does BidProof actually know about Godrej?" had no answer short of writing
SQL. Added a read-only companion to `inspect_pdf.py`:

```
python -m uv run --project apps/api python tools/show_company.py --company godrej
python -m uv run --project apps/api python tools/show_company.py --company godrej --gaps
```

Prints the radar profile, every company fact **with its own source line**, the
product catalogue, and then a GAPS section — because when a verdict says "needs
human", the cause is almost always a missing field here rather than a fault.

For Godrej today: 9 facts, 12 products, and **12 of 12 products with no lead time
and no price band, 9 of 9 facts with no expiry date.** That is precisely why the
matrix showed 10 of 11 rules queued for a human — the checker abstains instead of
guessing (SPEC §9 rule 3), exactly as designed.

Two bugs found writing it, both fixed:
- the gap counter used `is None` while the display used truthiness, so
  `price_band_inr = {}` printed UNKNOWN yet counted as present — 0 of 12 instead
  of 12 of 12. Both now share one `missing()` predicate.
- `--gaps` was declared in `argparse` and never honoured; it printed the full
  155-line dump. Now 18 lines.

Both tools are wired as VS Code tasks (**Company data** / **Company gaps**), which
prompt for the company name.

---

## "Upload failed: TypeError: Failed to fetch" (2026-07-28)

Reported with a screenshot. The message points at the network, and the network was
fine — every port was listening, CORS preflight returned 200, and a 7.6 MB PDF
uploaded in 1.1 s from outside the browser.

**The real cause was a stale organisation id.** A browser keeps the signed-in org
in `localStorage`, and the integration suite TRUNCATEs `organizations` — so after a
full test run the app is signed in as a company that no longer exists. Writing
against it reached the insert and died on a foreign key.

The part that made it unreadable: **an unhandled 500 carries no CORS header.**
Starlette's `ServerErrorMiddleware` sits outside `CORSMiddleware`, so the browser
cannot read the response and reports `TypeError: Failed to fetch`. Reproduced
exactly:

```
status: 500
access-control-allow-origin: *** MISSING ***
```

Three fixes:

1. **`main.py`** — a global `Exception` handler returns a JSON 500. Being *handled*
   means the response travels back out through the CORS middleware, so the real
   status reaches the client. Every server error in the app was previously
   indistinguishable from a network failure.
2. **`core/tenancy.py`** — `require_known_org()` returns **404 with a usable
   sentence** ("sign out and sign in again — its data may have been reset").
   Called on upload *after* the file check, so "this is not a PDF" still wins as
   the more specific answer.
3. **`apps/web/src/api.ts`** — `throwIfFailed()` clears the dead session on that
   404, so the app returns to sign-in instead of failing every request. Both fetch
   paths use it: `uploadTender` had its own `fetch` and would otherwise have been
   missed.

Verified on a spare port so the running dev server was left alone:

```
STALE org: 404  CORS=http://localhost:5173   "this organisation no longer exists…"
GOOD  org: 409  CORS=http://localhost:5173   (duplicate document — expected)
```

Regression test in `tests/test_upload_api.py`. Two existing tests caught a
first attempt that put the org check before the file check and turned a non-PDF
into a 404 instead of 415 — the order now reflects which answer is more specific.

Also fixed the same day: `test_console_api.py::test_full_run_records_every_agent_call`
never called `/extract` or `/check`, so extractor, matcher and riskscorer recorded no
runs. That was an omission from the earlier R2 change (extraction became opt-in and
the `/extract` + `/check` calls were inserted into the other tests but not this one).

---

## Source tags leaked into the exported proposal (2026-07-29)

Reported with a real exported document: the prose was full of `[F:f86aed8e]` and
runs of twelve `[P:...]` tags in a row.

Those are the proof chain. The ProposalWriter tags every factual sentence to the
company fact or catalogue product it came from, the FactChecker parses them, and each
claim's `source_tag` is derived from them — so they **must** stay in the stored
content. They must equally never reach a reader: a tender proposal handed to a buyer
with `[F:f86aed8e]` mid-sentence looks broken, and bids are rejected on presentation.

`render_for_reader()` in `services/proposal.py` strips them and tidies the debris —
`"certification , ISO"` back to `"certification, ISO"`, and the gap a run of twelve
tags leaves behind — while leaving paragraph breaks alone.

Wired in two places, deliberately **not** by stripping `content` itself:

- `services/export.py` — the .docx now renders the clean prose.
- `routers/proposal.py` — a new `content_display` field beside `content`. Keeping
  them separate matters: `editSection` exists (unused by the UI today), and if a
  future editor round-tripped stripped text it would silently destroy the
  provenance.
- `ProposalPanel.tsx` shows `content_display`; the claims list below still shows
  each `source_tag`, so provenance is visible as structured data rather than noise
  in the sentence.

Verified on the exact tender the user exported: **80 tags in stored content, 0 in the
display text, 0 in the rebuilt .docx.** Frontend test added
(`never shows the internal source tags in the prose`) — 88 web tests now.

## "The chatbot is not working"

Same session. Root cause: **Docker had died again**, so Postgres and LiteLLM were
both gone. `/organizations` was returning 500 (`ConnectionRefusedError`), and chat
fell back to the grounded-quote template. After restarting Docker the chat answers
properly, cites pages, and correctly says a figure is *not stated* rather than
inventing one.

**A real bug surfaced underneath it:** `availability.cached()` had no expiry, so the
first probe won forever. An API that starts while the LiteLLM container is still
booting cached `deterministic` and reported it for the rest of the process — the UI
badge claimed templates long after real models were reachable. A badge that lies
about whether an answer came from a model is worse than no badge. The cache now
expires after 60 s, so it self-heals; `?refresh=true` still forces it.

Confirmed: `mode: deterministic` (all three roles `ConnectError`) → after Docker came
back → `mode: live`, all three OK.

---

## An upload could disappear from the product (2026-07-29)

Reported: two files uploaded, both said parsed, neither visible in any radar tab.

`/radar` filtered `WHERE radar_list IS NOT NULL`. Triage assigns that list, and
triage runs **after** the parse, in a background task — so for as long as reading
takes, an upload existed in the database and appeared nowhere in the UI. A scanned
9-page PDF takes ~80 s through OCR, which is 80 s of a tender being simply gone. A
tender whose parse *failed* never got a list at all, so it stayed invisible for ever:
`GEM/2026/B/7583887` had been sitting unreachable.

Fixes:

- `/radar` now also returns untriaged tenders, in every tab — they have not been
  sorted into a lane, so they belong in all of them until they are.
- New `parse_status` on the card (the latest parse run's status), so the UI can say
  *which* of the three states a tender is in rather than showing a blank.
- `radar_list` became `str | None` on the response model. It had been declared `str`,
  so the first untriaged card raised a pydantic `ValidationError` → 500.

UI, in `App.tsx` + a new `ReadingIndicator` primitive:

- **being read** — an animated ring plus three pulsing dots, with the honest reason
  ("scanned pages go through OCR, which can take a few minutes");
- **could not be read** — says so, in danger colour, and points at the workspace;
- **read but not yet scored** — a quiet line, no spinner;
- **"Process with AI" is disabled while reading.** Pressing it mid-parse would have
  extracted from a document with no elements yet.
- The radar **polls every 4 s while anything is mid-parse** and stops when nothing
  is. Without that the card sat at "Reading…" until the user guessed and reloaded.

Verified live end to end: uploaded the user's own `2.0 ocr.pdf`, watched the radar
report `(untriaged) parse=running` for six consecutive polls, confirmed the browser
rendered one `reading-indicator` with `Process with AI` disabled, then confirmed it
became `needs_human / parse=succeeded` after ~80 s — with no reload.

## The chatbot refused "What is this tender"

Screenshot showed the most natural first question getting *"I can only discuss the
tenders in this workspace."*

`"what"`, `"this"` and `"tender"` are all in `_STOPWORDS`, so the question reduced to
**no searchable terms**, matched no element, and fell through the retrieval branch
into the hard refusal. Refusal has to mean "you asked about something else", never
"you asked broadly".

A question with no distinctive terms is now answered from the opening of the
document, which is where a tender states what it is. The scope boundary is untouched
for anything that *does* name other things. Verified live:

| question | result |
|---|---|
| What is this tender | answered, 6 citations — *"Supply, Installation & Commissioning of Pallet Racking System (p.1)"* |
| What is the EMD? | answered — *"Rs. 24,00,000/- … (p.6)"* |
| who won the cricket match yesterday | **refused**, `out_of_scope` |

Test added to `tests/test_chat_api.py` covering both halves in one tender (a second
upload of the same fixture is a duplicate document and returns 409, which is what
the first attempt tripped over).

---

## Portal expansion: reconnaissance before adapters (2026-07-30)

Asked to add scraping for IREPS, bank portals, CWC/FCI, seven PSUs, metros, AAI and
hospitals — ranked IREPS first. Recon was done before writing adapters, and it
changes the ranking.

### What each portal actually permits

| Portal | Status | Finding |
|---|---|---|
| **IREPS** (Railways) | ❌ **off-limits** | `robots.txt` is `User-agent: * / Disallow: /` — the entire site forbids automation |
| ONGC | ❌ | NIC eProcurement **with a captcha** on the listing page |
| IOCL / NTPC / Coal India | ⚠️ | NIC eProcurement. Listing rows are not served over HTTP, with or without a `JSESSIONID`, and not via the in-page navigation either — only the captcha-protected advanced search returns them |
| Bank of Baroda | ⚠️ | tender pages allowed by robots, but **every PDF disallowed** (`Disallow: /*.pdf$`), and the listing is JS-rendered with no table rows |
| PNB | ⚠️ | same shape: JS-rendered, 0 table rows |
| CWC (cewacor.nic.in) | ⚠️ | an ordinary website, not a NIC instance; needs its own page discovery |
| BHEL / SAIL | ❓ | `ConnectError` — the hostnames guessed here are wrong |
| DMRC / FCI | ❓ | pages fetched fine but contain no tender content at the URLs tried |

**So none of the fifteen is a cheap win.** Every one needs a browser, and most cap at
listing metadata — the same ceiling CPPP already hit. IREPS, the top-ranked
candidate, cannot be scraped at all without ignoring its robots.txt, which this
codebase will not do any more than it will solve a captcha.

### What was built anyway, because it is the right shape

Most Indian public buyers run **the same software** — NIC eProcurement — on their own
host. So `adapters/bidproof_adapters/niceproc/` is one adapter taking a
`NicPortal(name, host)`, and a new buyer is a line of config rather than a new file:

```
NIC_PORTALS=iocl:iocletenders.nic.in,ntpc:eprocurentpc.nic.in,coalindia:coalindiatenders.nic.in
NIC_PORTALS_ENABLED=false
```

The allow-list grew to seven hosts. An adapter still declares only its own host, so
it can never widen the SSRF boundary for itself.

**It is disabled by default and currently returns zero tenders**, which is the honest
state: the listing is not reachable. It is committed because the framework, the
config path, the allow-list entries and the tests are all real work that any future
attempt needs.

### The mistake worth recording

The first version reused CPPP's listing parser, which accepts any table row holding
a link. Run live against IOCL it returned **one "tender"** — actually a web
announcement, *"Restriction in IOCL E-Tendering Portal towards the number of
users"*. Inventing a tender out of site furniture is precisely the failure this
product exists to prevent, and it would have been shipped as a success.

`niceproc/parsing.py` is now strict: a row is a tender only if it carries a
`page=FrontEndViewTender` link. Re-run live, both portals now report **0** instead of
a fabrication. Two tests pin it, one of them using the exact announcement text.

### Recommended order, revised

1. **GeM** — already working, and the only source whose documents are fetchable.
2. **CPPP** — already working, listing only.
3. **Bank portals** — best remaining target. Robots-permitted, and they cover
   Security Solutions (safes, vaults, lockers), which currently has **zero** sources.
   Needs a browser and per-bank parsing; treat BoB's PDF ban as binding.
4. **CWC / FCI** — highest category relevance (warehouse racking), but the tender
   pages still need finding.
5. **NIC PSU instances** — framework is in place; blocked on the captcha, so only
   worth revisiting if a public listing endpoint is found.
6. **IREPS** — do not. Their robots.txt forbids it.

### Two portals that DO work: CWC and PNB (2026-07-30)

Asked to show tenders and link out even where the PDF cannot be fetched — the CPPP
pattern. Two buyers turned out to publish an ordinary HTML table, needing no captcha
and disallowed by no robots rule. `adapters/bidproof_adapters/htmlportal/` is one
config-driven adapter for both, verified live:

| | CWC (cewacor.nic.in) | PNB (pnbindia.in) |
|---|---|---|
| tenders found | real rows with references, titles, locations | **29** |
| closing date | parsed (`24-08-2026 03:00:00 PM`) | portal publishes none |
| per-tender link | ✅ **durable** — `/Home/ViewTenderData?TenderID=…` | ❌ ASP.NET `__doPostBack`, so no tender has a URL |
| card links to | the tender itself | the listing page |

CWC is the first Indian portal found whose tender link is an **address rather than a
session ticket**, so "open on portal" genuinely works there — unlike CPPP. It is also
the closest category match Godrej has: warehouses mean racking. PNB covers safes,
vaults and lockers, the Security Solutions category, which had **no source at all**.

Both are `html_portals_enabled: false` by default — each costs a browser render per
cycle. Documents are never fetched by design: Bank of Baroda's robots.txt disallows
every `*.pdf`, so this family lists and links out exactly as CPPP does.

Seven tests, including one that pins the "Sort by Relevance" control row and the
header **not** becoming tenders, and one that a closing date which cannot be parsed
stays absent rather than being guessed — a wrong deadline could lose a bid.

### Captcha bypass: declined

Asked whether a tool could bypass the captcha on the NIC PSU portals. It was not
attempted and no such tool was added. A captcha is the operator's explicit statement
that automation is unwelcome, and this codebase already treats it that way for CPPP;
defeating it would also put the pilot on the wrong side of those portals' terms. The
NIC PSU instances therefore remain unreachable, and the framework for them stays
disabled rather than being made to work by force.

### Godrej's own logo in the shell (2026-07-30)

`apps/web/public/godrej-logo.png` (600×600, 61 KB), with
`seed_godrej_public.py` setting the branding so a reseed keeps it:

```json
{"logo_url": "/godrej-logo.png", "primary_color": "#C7017F"}
```

Served by Vite from `public/`, so it works offline and is version-controlled with
the code rather than hot-linked. `primary_color` is the crimson from the mark
itself, which `OrgBadge` uses for the monogram if the image ever fails to load —
a missing file degrades to initials instead of breaking the shell.

Verified live: `/godrej-logo.png` serves 200 `image/png` 61,192 bytes, both badges
render as `IMG` with `naturalWidth 600` and `loaded: true`, and `npm run build`
copies it into `dist/`. 88 web tests pass.

---

## Why both radar lists were always empty (2026-07-30)

Asked what "In our lane" and "Opportunity radar" are for, since nothing ever
appeared in them. They were empty because of an arithmetic bug, and the second one
would have filled with noise once fixed. Both are now corrected.

### Bug 1 — misspelled weight keys halved every tender's confidence

`seed_godrej_public.py` wrote the fit weights as `category_fit` / `value_band` /
`past_wins`. The scorer reads `category` / `eligibility` / `value` / `location` /
`win_history`. `_profile_from_row` merged them:

```python
weights={**default_weights, **(row.weights or {})}
```

Different key names, so nothing was overridden — three junk keys were **added**:

```
real  category .35  eligibility .25  value .15  location .10  win_history .15  = 1.00
junk  category_fit .4   value_band .3   past_wins .3                           = 1.00
                                                          total_weight  = 2.00
```

`coverage = known_weight / total_weight` = `0.90 / 2.00` = **0.45**, against a
`confidence_floor` of 0.50. Every tender failed the floor and went to the human
queue, permanently. The fit score itself was always right — only the denominator
was wrong, which is why the numbers looked plausible.

Fixed in two places, because either alone would have left the trap armed:
* the seed now uses the scorer's own key names;
* `_known_weights()` drops unrecognised keys and logs them, so a future typo can
  no longer reach the coverage arithmetic.

### Bug 2 — the relevance threshold was never applied

`thresholds.radar` (0.45) was consulted only to pick the borderline comparison
point. Membership fell through to `else: OPPORTUNITY_RADAR`, so **every**
confidently-scored tender outside the lane became an "opportunity". After fixing
bug 1, that put a Punjab National Bank request for *"suitable ready premises"* on
the radar at fit **0.10**.

The radar is meant to be the tenders you *could* win but never bid on. Anything
below `thresholds.radar` is now `not_relevant` — kept for audit, hidden from the
default radar view, still reachable with `?list=not_relevant`. Migration **0022**
widens the `ck_tenders_radar_list` CHECK; its downgrade moves such rows back to
`needs_human` rather than dropping them.

### Result, re-triaging the 57 live tenders

| list | n | avg fit |
|---|---|---|
| **in_our_lane** | **2** | 0.66 |
| needs_human | 52 | 0.14 |
| not_relevant | 3 | 0.21 |

The two in-lane tenders are both genuine storage-racking work (a GeM bid and a CWC
storage-space offer). `opportunity_radar` is legitimately empty for this batch:
nothing scored 0.45–0.55 outside the lane.

### Why 52 still abstain — and the one lever that moves them

Of the 52: 35 fail on coverage, 17 are borderline. Signals unknown across them:

| signal | unknown |
|---|---|
| value | 52 of 52 |
| location | 52 of 52 |
| win_history | 50 |
| eligibility | 35 |

* **value** — portal listings do not publish a tender value, and a listing-only
  tender has no document to read one from. It becomes known after the PDF is
  fetched and parsed.
* **location** — `org_profiles.locations` is `[]`, so this signal can *never*
  score. That is 0.10 of coverage lost on every tender in the system, for free.
  Filling it is the cheapest single improvement available.
* **eligibility** is still explicitly provisional in the scorer ("the real
  rule-by-rule check against the capability DB is Week-3 work"), so it improves
  only when value or a closing date is known — not from the capability database.

Worth noting for expectations: triage runs after a *parse*, never after
`/extract`, `/check` or a proposal. So processing a tender with AI and generating
proposals genuinely cannot change its radar list today — re-triage on those events
is the obvious follow-up, and is not yet wired.

Three tests added to `tests/test_triage_scoring.py`, including one that pins the
weights arithmetic and one using the real PNB title that was misfiled. 197 fast
tests pass.

---

## Evaluation: real measurement per component (2026-07-30)

Asked for a tab measuring accuracy for every tool — extraction, Docling,
pypdfium2, OCR, scraping, RAG, proposals — with the explicit requirement that the
numbers be real, because improving accuracy depends on them.

### The starting position, checked rather than assumed

The suspicion was "it's hardcoded for LLMs". Half right, and the half that was
wrong matters:

* The **Analytics screen is already honest** — it carries `is_this_honest` flags
  and prints "Not calibrated yet" instead of drawing an invented curve.
* `tests/goldset_harness.py` is a **real** harness over 25 labelled cases. But the
  cases are **synthetic**, generated alongside the extractor's own patterns, which
  is why every figure in `eval_report.json` is exactly 1.00. That is not accuracy;
  it is a regression check wearing accuracy's clothes.
* There is **no embedding retrieval in the product at all** — the librarian has
  only `blocks.py`, and Ask BidProof scores elements by keyword overlap. "RAG
  evaluation" had nothing to evaluate.

### The design rule

A number is only useful if its provenance travels with it, so `GroundTruth` is
part of the type, not a comment: `human_labelled`, `synthetic`, `derived`,
`self_reported`, `none`. Every metric also carries its sample size and whether
higher is better — a character error rate coloured like an accuracy is a lie told
in green. `Status.NO_GROUND_TRUTH` and `NOT_IMPLEMENTED` are first-class results
that render as themselves and say what would be needed instead.

### What is measured, and how

| Component | Ground truth | Result on this machine |
|---|---|---|
| **OCR (RapidOCR)** | **synthetic, exact** | **CER 0.88 %**, words 93.2 %, **figures 100 %** |
| **Scraping** | derived | cppp 1.00, cwc 1.00, gem 0.667, pnb 0.667 field completeness |
| **Rule extraction** | synthetic | P/R/F1 1.00 — caveated, see below |
| **Proposals** | self-reported | no sections generated yet |
| **Text engines** | derived | Docling vs pypdfium2: characters, pages lost, time |
| **Retrieval** | none | `not_implemented`, with the file format to add later |

**OCR is the strongest addition.** Ground truth is generated by rendering known
sentences — rupee amounts, clause numbers, dates, ISO standards — then flattening
the page to an image so no text layer survives. The correct answer is known
exactly, so character error rate is a true measurement rather than an estimate.
Its limit is reported with it: clean rendered text is an upper bound, not a
smudged photocopy. Measured: **0.88 % CER, and all six figures read exactly** —
which is the number that actually matters, since a bid turns on an EMD amount.

**Text engines needs no labels at all.** Running Docling and pypdfium2 over the
same pages answers the question that matters — is the heavy engine returning more
than the cheap one, and how often does it hand back nothing for a page that
demonstrably has text. On this project that is not hypothetical: Docling hit
`std::bad_alloc` on a real tender and silently lost pages.

**Scraping is immediately diagnostic.** GeM and PNB sit at 0.667 field
completeness against CPPP and CWC at 1.00 — visible in one line, where before it
would have taken a query to notice.

### What is deliberately not claimed

* Rule extraction reports `synthetic` and carries the caveat in the card, not a
  footnote: these scores prove the extractor has not regressed, not that it reads
  real tenders. The fix is stated — replace the gold PDFs with real tenders and
  hand-label them; ten real cases beat a hundred synthetic.
* Retrieval reports `not_implemented`. A recall@k of 0.0 would read as "our
  retrieval is terrible" rather than "there is no retrieval", so no number is
  produced at all.
* An evaluator that crashes returns `ERROR` with the exception, never a zero.

### Shape

```
apps/api/app/services/evaluation/
    types.py      Status, GroundTruth, Metric, Evaluation
    readers.py    OCR character error rate; Docling vs pypdfium2
    pipeline.py   extraction, scraping, proposals, retrieval
    registry.py   what exists, fast vs slow, run_one / run_all
apps/api/app/routers/evaluation.py    GET /evaluation/catalogue, POST /evaluation/run
apps/web/src/screens/Evaluation.tsx   the tab
```

The two expensive evaluators (OCR, text engines) are opt-in behind "Run
everything", and a test pins that they can never run because someone opened a
screen.

**205 backend tests** (8 new), **88 web tests**, `tsc` clean. Verified end to end
through the live API.
