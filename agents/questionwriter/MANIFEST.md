# Agent: QuestionWriter

| Field | Value |
|---|---|
| **Name** | QuestionWriter |
| **Single job** | For every mandatory rule we fail, draft a formal pre-bid letter asking the buyer to relax or clarify it — citing the clause and page — so "cannot bid" can become "can bid". |
| **Inputs** | Failed rules (verdict GAP) with their grounded clause text + page + el_id, the company name, and the pre-bid query deadline. |
| **Outputs** | `LetterDraft` per failed rule: subject, body, and the citation it is grounded on (`el_id` + page). Always a DRAFT. |
| **Model role** | strong — polishes the phrasing only. The draft is built deterministically from the grounded clause; a polished body that drops the page citation is rejected and the grounded template is kept (facts from data, style from the model — §9 rule 5). |
| **Tools** | none. It has NO ability to send email, submit, or reach the network — structurally, not by policy. A human sends every letter. |
| **Guardrails** | Every letter cites a real clause + page (§9 rule 1). Least privilege (SPEC §10): drafts only. Nothing is ever sent by the system — there is no send function and no send endpoint. |
| **Test set** | `tests/test_questionwriter.py`, `tests/test_questions_api.py` |
