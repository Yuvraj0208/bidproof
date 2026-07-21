"""The registry of production, model-facing prompts (US-16, SPEC §14).

Prompts are versioned like code. `active_prompts()` collects every prompt an
agent actually sends to a model, with its content hash. A change to any of
them changes its hash — and the prompt-approval gate (tests) fails until the
change is reviewed and re-approved, having passed the gold-set tests.
"""

import hashlib

from bidproof_extractor.prompts import EXTRACTOR_PROMPT_V1, VOTE_PROMPT_V1
from bidproof_matcher.judge import JUDGE_PROMPT_V1
from bidproof_proposalwriter import WRITER_PROMPT_V1
from bidproof_questionwriter import QUESTION_PROMPT_V1


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def active_prompts() -> dict[str, str]:
    """prompt_id -> sha256 of the exact text sent to the model."""
    return {
        "extractor_v1": _hash(EXTRACTOR_PROMPT_V1),
        "extractor_vote_v1": _hash(VOTE_PROMPT_V1),
        "judge_v1": _hash(JUDGE_PROMPT_V1),
        "writer_v1": _hash(WRITER_PROMPT_V1),
        "question_v1": _hash(QUESTION_PROMPT_V1),
    }


def unapproved_prompts(
    active: dict[str, str], approved: dict[str, dict]
) -> list[str]:
    """Prompt ids whose current hash does not match an approved hash — i.e.
    changed without review, or never approved."""
    offenders = []
    for prompt_id, current_hash in active.items():
        record = approved.get(prompt_id)
        if record is None or record.get("sha256") != current_hash:
            offenders.append(prompt_id)
    return offenders
