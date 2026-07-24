# BidProof — finishing status

Progress file for the demo-readiness push. Work the tasks **in order**; tick each item
with a one-line note when its tests pass and it is committed.

Environment note: Docker Desktop on this machine is unstable — if the API 500s with
`ConnectionRefusedError [WinError 1225]`, restart `bidproof-postgres-1` and retry.

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
- [ ] Gateway wiring verified for small/mid/strong; loud startup failure when keys missing
- [ ] Mode (real-model vs deterministic) surfaced in the UI
- [ ] Rule extraction: full text, clause number, family, obligation type, numeric threshold
- [ ] Verdicts: reasoned justification citing tender element + company record
- [ ] Risk register: per-clause ₹ impact + why it matters
- [ ] Pre-bid letters: formal Indian government correspondence
- [ ] Proposal: long, structured, section-by-section, still fully source-tagged (fixes D1, D2)
- [ ] Chat: real reasoning over this tender's elements with page citations (fixes D3)
- [ ] Show sample output: proposal, one pre-bid letter, three verdicts

### Task 3 — Fix everything from the audit
- [ ] Work down D1–D14 not already covered by Task 2; list anything unfixable with reason

### Task 4 — The interface
- [ ] Tokens (Tailwind config + CSS vars), Inter, tabular numerals, 8px grid, shadows, focus ring
- [ ] AppShell: indigo sidebar (ten screens), top bar with tender context + countdown + search
- [ ] Primitives + `/kitchen-sink`: Card, PageHeader, DataTable, StatCallout, CountdownChip,
      VerdictBadge, RiskTag, ConfidenceChip (restyle only), EmptyState, SkeletonLoader, Toast, Modal, Tooltip
- [ ] Retrofit screens in spine order: Radar → Workspace → Matrix → Decision Room → Agent Console
      → Proposal Studio → Model Lab → remaining panels
- [ ] Loading / empty / error state on every screen

### Task 5 — Missing screens
- [ ] Analytics (funnel, TAT, DQ-risks, coverage-accuracy, calibration, cost trend, KPI vs baseline)
- [ ] Admin (roles, prompt approvals, model config, thresholds, budgets, audit log, scraper health, kill switch)

### Task 6 — Real demo data
- [ ] Seed script: tenders at several pipeline stages, capability DB, catalogue, library, worked
      amendment, completed run with real console numbers
- [ ] One-command reset, documented in README

### Task 7 — Final QA
- [ ] web tests, api tests, gold-set harness, attack suite — all results shown
- [ ] Every screen re-walked; §17 UX principles checked; 1080p + 1440p verified
- [ ] Demo-readiness report (Week-3 spine, what works, what's weak, §19 targets confirmed)
