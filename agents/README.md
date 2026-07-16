# agents/

One folder per agent (SPEC §4). **Write the manifest before the agent.**

Every agent ships a one-page `MANIFEST.md`:

| Field | Meaning |
|---|---|
| Name | e.g. Extractor |
| Single job | One sentence. One job only. |
| Inputs | Typed shared state it reads |
| Outputs | The strict JSON schema it must return |
| Model role | small / mid / strong (never a vendor or model name) |
| Tools | The tools it may use — least privilege (SPEC §10) |
| Guardrails | Input fencing, schema validation, citation check, budgets |
| Test set | Where its own tests live |

Rules that apply to every agent: talk only through typed shared state, fit
the schema or be rejected, cite `el_id + page + bbox` or be thrown away,
never do arithmetic, never export/email/submit/delete.
