# Agent: Triage

| Field | Value |
|---|---|
| **Name** | Triage |
| **Single job** | Assign every discovered/uploaded tender a fit score and a list — In Our Lane, Opportunity Radar, or the Checkpoint-0 human queue — and explain itself on every card. |
| **Inputs** | Tender signals (title, parsed element text, extracted ₹ value, closing date) + the org's profile (categories, weights, value band, locations, win history). |
| **Outputs** | `TriageResult`: list, fit 0–1, per-component breakdown, confidence + band, human-readable reasons, Checkpoint-0 state. |
| **Model role** | small (reserved for semantic category matching later). v1 is fully deterministic: keyword matching + config weights. All numbers — fit, value, days-to-close — are plain code; a model never does arithmetic (§9 rule 2). |
| **Tools** | none. Pure computation over typed inputs. |
| **Guardrails** | Fit = w1·category + w2·provisional-eligibility + w3·value-band + w4·location + w5·win-history with weights from tenant config, renormalised over the components actually known — unknowns lower confidence, they are never guessed (§9 rule 3). Too little known, or a fit inside the borderline margin → NEEDS HUMAN (Checkpoint 0). Only a confident List-A verdict auto-passes (SPEC §7 row 0). Rupee values come from regex extraction only. |
| **Test set** | `tests/test_triage_scoring.py`, `tests/test_radar_api.py` |
