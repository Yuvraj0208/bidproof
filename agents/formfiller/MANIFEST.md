# Agent: FormFiller

| Field | Value |
|---|---|
| **Name** | FormFiller |
| **Single job** | Fill the standard declarations a bid requires from real company data only. Anything it cannot source, it leaves blank and flags — it never guesses on a legal declaration. |
| **Inputs** | A declaration template (named fields, each with a data source) and a context of verified values built from the capability database. |
| **Outputs** | `FilledDeclaration`: each field either filled (with its value and source) or blank and flagged for a human. |
| **Model role** | templates — no model, ever. Filling a legal declaration is deterministic lookup, not generation, so a hallucinated value is structurally impossible. |
| **Tools** | none. The app service hands it a read-only value context; it cannot reach the database, the network, or a model. |
| **Guardrails** | A field whose source value is missing or blank is left **blank and flagged** ("a human must complete this") — never inferred, never defaulted. Fields that are a human's act to complete (signatory, place, date) are always flagged. Every filled value carries the source it came from. |
| **Test set** | `tests/test_formfiller.py`, `tests/test_declarations_api.py` |
