"""US-16 prompt-approval gate (SPEC §14): every production prompt must match
its approved hash. A prompt change fails this gate until re-approved — the
CI-level demonstration that a bad prompt change is blocked."""

import json
from pathlib import Path

from app.prompts_registry import active_prompts, unapproved_prompts

APPROVALS = (
    Path(__file__).resolve().parents[1] / "infra" / "prompt_approvals.json"
)


def _approved() -> dict:
    data = json.loads(APPROVALS.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def test_every_production_prompt_is_approved():
    offenders = unapproved_prompts(active_prompts(), _approved())
    assert offenders == [], (
        "these prompts changed without approval — update infra/"
        f"prompt_approvals.json after the gold-set passes: {offenders}"
    )


def test_a_changed_prompt_is_detected():
    # Simulate a production prompt being edited: its hash no longer matches.
    active = dict(active_prompts())
    active["judge_v1"] = "a" * 64   # tampered hash
    offenders = unapproved_prompts(active, _approved())
    assert offenders == ["judge_v1"]


def test_a_new_unlisted_prompt_is_flagged():
    active = dict(active_prompts())
    active["brand_new_prompt"] = "deadbeef" * 8
    offenders = unapproved_prompts(active, _approved())
    assert "brand_new_prompt" in offenders


def test_approvals_record_the_gold_set_gate():
    # Re-approval is only legitimate once the gold set passes — the record
    # carries that fact, tying prompt changes to measured accuracy.
    for prompt_id, record in _approved().items():
        assert record["sha256"]
        assert record["gold_set_passed"] is True
        assert record["approved_by"]
