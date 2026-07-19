# Agent: Extractor

| Field | Value |
|---|---|
| **Name** | Extractor |
| **Single job** | Pull every requirement rule out of a parsed tender — across the 5 families (eligibility, technical, commercial, legal, submission) — with proof for each one. |
| **Inputs** | The tender's grounded elements `(el_id, page, bbox, text)`. Nothing else. |
| **Outputs** | Rules, each carrying `family, key, requirement_text, value, el_id, confidence, band, reason, status`. A rule without a real `el_id` cannot exist — enforced by schema AND by a foreign key in the data layer. |
| **Model role** | mid (via the gateway only). The pattern side uses no model at all. |
| **Tools** | none beyond the gateway. No DB, no network, no files — the app service wires persistence. |
| **Guardrails** | Two extractors side by side (SPEC §5.3): (a) regex for anything exact — an AI never guesses a number a regex can find (§9 rule 2); (b) the model filling a STRICT JSON schema, citing an el_id per rule, with document text fenced as data (§11.1) — malformed output is rejected and retried, never patched (§9 rule 6). They are compared by deterministic code; disagreement → the model votes 3×; still split → NEEDS HUMAN (§9 rule 3). Then the ground-check: any rule not traceable to a real element, or citing an element that does not contain its value, is THROWN AWAY, not down-scored (§9 rule 1 — also the anti-injection filter, §11.1). |
| **Test set** | `tests/test_extractor.py`, `tests/test_rules_api.py` |

**Prompts are versioned like code** (SPEC §14): `bidproof_extractor/prompts.py`
holds `EXTRACTOR_PROMPT_V1`. Changing it is a reviewed code change gated by the
gold-set tests once they exist (Week 2).

**Degradation:** with no model configured, the pattern side still extracts every
exact value with full grounding; the AI side records "model unavailable". The
demo spine (click-to-proof) never depends on a live model.
