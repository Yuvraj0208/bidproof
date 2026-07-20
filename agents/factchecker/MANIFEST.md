# Agent: FactChecker

| Field | Value |
|---|---|
| **Name** | FactChecker |
| **Single job** | Split the draft into claims and mark each one **verified**, **cannot_verify**, or **contradicted** against the tagged fact context. |
| **Inputs** | Section text with source tags, and the fact context (`tag -> fact text`) the writer drew from. |
| **Outputs** | Per-claim results with status and the cited tag; a section's verified-percentage. |
| **Model role** | mid (reserved for semantic claim checking later). v1 is deterministic digit verification: a claim's numbers must literally appear in its cited fact — the same normalisation the Extractor's ground-check uses (§9 rule 2). |
| **Tools** | none. |
| **Guardrails** | A claim citing an unknown tag, or stating numbers with no tag at all, is **cannot_verify** — a human must add a source. A claim whose numbers disagree with its cited fact is **contradicted** — and contradicted claims block export (US-10, SPEC §5.7). Style sentences are not claims. |
| **Test set** | `tests/test_factchecker.py`, `tests/test_proposal_api.py` |
