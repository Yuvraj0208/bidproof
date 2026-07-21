# Agent: Guard

| Field | Value |
|---|---|
| **Name** | Guard |
| **Single job** | Screen every input and output for instruction-like / jailbreak text before it is trusted (SPEC §10, §11). |
| **Inputs** | Any text — a chat question, a chat answer, or document text. |
| **Outputs** | `GuardVerdict`: flagged or clean, a category, and the phrase that tripped it. |
| **Model role** | small (a guard classifier such as Llama-Guard/PromptGuard class). v1 is deterministic pattern rules; the small model layers on behind the same interface. |
| **Tools** | none — pure text screening. |
| **Guardrails** | Document text is data, never instructions (§9 rule 4). A flagged input is shown to the human and treated as inert; it never steers the system. The chat uses the Guard on both the question and the answer, and out-of-scope questions are hard-refused — refusal is a security feature, not rudeness (§11.2). |
| **Test set** | `tests/test_guard.py`, `tests/test_chat_api.py` |
