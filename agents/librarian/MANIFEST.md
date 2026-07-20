# Agent: Librarian

| Field | Value |
|---|---|
| **Name** | Librarian |
| **Single job** | Chop past proposals into reusable, tagged blocks — outcome recorded — and hand the ProposalWriter the best ones, winning blocks first. |
| **Inputs** | Proposal text + its outcome (won / lost / synthetic) + provenance; at retrieval time, a section tag and tender context. |
| **Outputs** | `LibraryBlock`s: section tag, text, outcome, source. Retrieval returns a ranked shortlist. |
| **Model role** | mid (reserved for semantic chunking later). v1 chops by heading heuristics and ranks by outcome weight + keyword overlap — deterministic. BGE-M3 hybrid slots in behind the same interface (SPEC §5.7). |
| **Tools** | none. Pure text processing; persistence is the app service's job. |
| **Guardrails** | Poisoning defence (SPEC §11.3): every block added through the API is **quarantined by default** and never retrieved until approved — only role-approved users lift quarantine (roles arrive in US-16). The starter set is synthetic, clearly tagged `outcome='synthetic'`, swapped for real proposals later. Every block carries provenance. |
| **Test set** | `tests/test_librarian.py`, `tests/test_proposal_api.py` |
