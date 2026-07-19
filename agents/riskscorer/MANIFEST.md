# Agent: RiskScorer

| Field | Value |
|---|---|
| **Name** | RiskScorer |
| **Single job** | Find the clauses that can hurt, and price them in rupees where the arithmetic allows. |
| **Inputs** | Grounded rules, tender value (regex-extracted, may be unknown), closing date, and the org's catalogue lead times + risk thresholds. |
| **Outputs** | Flags `{code, severity, message, rupee_impact, el_id}` — every flag cites the element behind it when one exists. |
| **Model role** | rules (pure code) now; mid reserved for later semantic flags. |
| **Tools** | none. |
| **Guardrails** | All rupee impacts are plain arithmetic (§9 rule 2). A flag that cannot be computed from known inputs is simply not emitted — unknown inputs never fabricate a risk or an all-clear. |
| **Implemented flags** | `pbg_too_high` (₹ = % × tender value), `oversized_emd` (vs % of tender value), `delivery_infeasible` (required < best catalogue lead time), `query_deadline_passed` (window vs closing date). |
| **Deferred** (need extraction patterns / corpus that do not exist yet) | penalty-rate-too-high, weird escalation formula, spec-written-for-a-competitor (needs rival datasheet corpus + embeddings — Week 6 territory). Declared here so nobody mistakes absence for coverage. |
| **Test set** | `tests/test_riskscorer.py`, `tests/test_checking_api.py` |
