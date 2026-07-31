# Agent: Conductor

| Field | Value |
|---|---|
| **Name** | Conductor |
| **Single job** | Orchestrate the specialist agents: run what can run together, stop at every human checkpoint, and record what each step cost. |
| **Inputs** | `org_id`, `tender_id`. Everything else is re-derived from Postgres at the start of a run, so a resumed run needs nothing carried over from the last one. |
| **Outputs** | `BidState` — typed references (rule ids, verdict ids, risk codes, the decision) plus a per-node trace. Never prose, never payloads. |
| **Model role** | none. The Conductor calls no model itself; it schedules agents that do. Routing is deterministic code, so a model can never choose to skip a checkpoint. |
| **Tools** | LangGraph (graph construction, superstep scheduling, `interrupt`). The database, through the existing org-scoped session only. |
| **Guardrails** | State is a pydantic model with `extra="forbid"`, so a malformed node return is rejected rather than patched (§9 rule 6). Nodes hold no logic — each calls one existing service — so the graph cannot become a second implementation. No node imports export, submission, mail or delete (rule 8). The `decide` node has no gateway parameter and constructs none (rule 3). |
| **Checkpoints** | 4, 5 and 6 are `interrupt()` nodes with a single edge to the end of the graph. There is no branch that could auto-pass one — SPEC §7 stated as a shape rather than a policy. |
| **Parallelism** | Matcher ∥ RiskScorer, per SPEC §4. Safe because the RiskScorer reads rules and never verdicts (`checking._build_risk_inputs` touches only the rule half of its pairs), and because the two nodes write disjoint state keys. Honest note: the pair saves milliseconds — the RiskScorer is arithmetic. The wall-clock win is inside the `match` node, where the cited judge fans out over prose rules under `LLM_MAX_CONCURRENCY`. |
| **Not built yet** | Durable checkpointing across a process restart (needs a saver over the existing asyncpg session — LangGraph's stock Postgres saver opens its own pool and would sit outside row-level security). Checkpoints 5 and 6 as graph nodes. Extraction and proposal stages. Declared here so nobody mistakes absence for coverage. |
| **Test set** | `tests/test_conductor.py`, `tests/test_matcher_concurrency.py`, `tests/test_process_wiring.py` |
