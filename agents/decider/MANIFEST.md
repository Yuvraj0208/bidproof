# Agent: Decider

| Field | Value |
|---|---|
| **Name** | Decider |
| **Single job** | Turn verdicts + risks into a bid/no-bid answer **in rupees**, with the maths shown term by term — and then stop, because Checkpoint 4 belongs to a human. |
| **Inputs** | Verdicts (for the hard gate), rule values (EMD, PBG), tender value, and the EV configuration (config weights, sponsor-validated §16). |
| **Outputs** | The decision: hard-gate result, EV terms `[{label, formula, value_inr}]`, EV total, GO / NO_GO / NEEDS_HUMAN recommendation, and a confidence on the recommendation itself. |
| **Model role** | none — deterministic (SPEC §4). Every number here is plain code. |
| **Tools** | none. |
| **Guardrails** | Hard gate first: any failed mandatory eligibility rule → NO, regardless of EV (a human may override WITH a written reason, logged). `EV = P(win)·profit − (man-days·loaded rate + cost of money locked in EMD/PBG)` — a rupee figure a CFO can argue with, not a score out of ten. Unknown tender value → NEEDS_HUMAN, never a guessed EV (§9 rule 3). **Checkpoint 4 never auto-passes**: every decision is born `pending_signoff` and a named human signs it; overrides carry a written reason into the append-only audit log (§9 rules 7, 9). |
| **Test set** | `tests/test_decider.py`, `tests/test_decision_api.py` |
