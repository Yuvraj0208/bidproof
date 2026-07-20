# Agent: ProposalWriter

| Field | Value |
|---|---|
| **Name** | ProposalWriter |
| **Single job** | Draft the proposal, section by section — facts from the capability database only, every factual sentence carrying a source tag. |
| **Inputs** | The tagged fact context (each capability fact/product rendered with its `[F:…]`/`[P:…]` tag), the tender's requirements, ranked library blocks for style, and the section list. |
| **Outputs** | Section drafts in which every factual sentence ends with a valid source tag. |
| **Model role** | strong — style only (§9 rule 5). The model receives fenced facts and must copy tags verbatim; without a model, deterministic templates produce the same grounded output. |
| **Tools** | none. The ProposalWriter cannot touch the database (SPEC §10) — the app service hands it a read-only fact context. |
| **Guardrails** | Enforcement, not hope: after generation, `enforce_source_tags` DROPS any factual sentence (it contains numbers) whose tag is missing or unknown — thrown away and counted (§9 rule 1). Style sentences pass untagged. **The tender's format wins**: an explicit tender-dictated section list overrides the default government template; automatic format detection from parsed rules is deferred until real tender examples exist (gold set) — noted here so absence is not mistaken for coverage. |
| **Test set** | `tests/test_proposalwriter.py`, `tests/test_proposal_api.py` |
