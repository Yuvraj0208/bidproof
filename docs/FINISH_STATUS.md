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
- [ ] Work down D1–D14 not already covered by Task 2; list anything unfixable with reason

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
- [ ] Seed script: tenders at several pipeline stages, capability DB, catalogue, library, worked
      amendment, completed run with real console numbers
- [ ] One-command reset, documented in README

### Task 7 — Final QA
- [ ] web tests, api tests, gold-set harness, attack suite — all results shown
- [ ] Every screen re-walked; §17 UX principles checked; 1080p + 1440p verified
- [ ] Demo-readiness report (Week-3 spine, what works, what's weak, §19 targets confirmed)
