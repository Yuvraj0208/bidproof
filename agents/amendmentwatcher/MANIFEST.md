# Agent: AmendmentWatcher

| Field | Value |
|---|---|
| **Name** | AmendmentWatcher |
| **Single job** | When a corrigendum arrives, work out exactly what changed, re-check only the affected rules, and report the new EV — without reprocessing the whole tender. |
| **Inputs** | A corrigendum PDF for an existing tender; the tender's current grounded rules and its prior decision. |
| **Outputs** | An `Amendment` record: the cited change list (`old→new`, page), the rules affected, the rules that broke, and the EV before vs after — plus a one-line alert. |
| **Model role** | none — it orchestrates existing agents. Parsing reuses the Parser ladder; extraction reuses the dual extractor; re-checking reuses the Matcher; the EV reuses the deterministic Decider. |
| **Tools** | none of its own — it composes Parser + Extractor + Matcher + Decider through typed shared state. |
| **Guardrails** | The corrigendum is a new grounded document version (§9 rule 1): a revised rule is re-grounded to the corrigendum's page + box. A corrigendum **supersedes** every prior occurrence of a revised key, so the tender never holds two contradictory values. Only the affected rules are re-checked (SPEC §5.1); risks are re-derived deterministically. The tender value is held stable across corrigenda (a corrigendum carries no contract value) so the EV moves only for the reasons the corrigendum actually changed. |
| **Test set** | `tests/test_amendment_api.py` |
