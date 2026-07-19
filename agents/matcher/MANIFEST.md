# Agent: Matcher

| Field | Value |
|---|---|
| **Name** | Matcher |
| **Single job** | Check every extracted rule against what the company actually has, and return one of five verdicts: COMPLIES / PARTIAL / GAP / NOT APPLICABLE / NEEDS HUMAN. |
| **Inputs** | Grounded rules (each citing its el_id) + the org's capability records (facts and catalogue products, each carrying provenance). |
| **Outputs** | One verdict per rule: `{verdict, reason, confidence, arithmetic, cited_fact_id / cited_product_id}`. The verdict row keeps its FK chain: verdict → rule → element → page+box. |
| **Model role** | deterministic + mid. Numeric rules are checked by plain-code arithmetic — the checker functions do not accept a model handle, so calling one is structurally impossible (§9 rule 2). Only prose spec-match rules reach the judge, via the gateway. |
| **Tools** | none beyond the gateway (judge path only). |
| **Guardrails** | The judge fills a strict JSON schema and is **VOID unless it cites BOTH** the tender element and a retrieved product record (SPEC §5.5) — a voided judge means NEEDS HUMAN, never a guess (§9 rules 1, 3). Retrieval defaults to deterministic keyword overlap; the BGE-M3 hybrid + bge-reranker upgrade slots in behind the same `CandidateRetriever` interface when installed (heavy extra, like Docling/PaddleOCR). Missing capability data yields NEEDS HUMAN, not an assumed pass. |
| **Test set** | `tests/test_matcher.py`, `tests/test_checking_api.py` |
