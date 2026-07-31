"""Resolving a flagged claim — the missing half of Checkpoint 5.

SPEC §7 requires a human to "resolve every flag" before approving a proposal
section, and the export blocker refuses while any claim is contradicted. But
nothing in the product could resolve one: the approve button was disabled with
the tooltip "resolve open flags first", and there was no control that did it.
A flagged section could not be approved and could not be exported except by
overriding the entire export — the heaviest instrument in the product, for a
problem it was not meant to solve.

Two resolutions, because there are two honest answers:

* **drop** — the writer claimed more than the company can show, so the sentence
  comes out of the proposal. The prose is edited, not just the badge.
* **accept** — the claim is true but the capability database cannot prove it.
  The sentence stays on a named person's word, with a written reason, in the
  audit log.
"""

import pytest

from app.services import proposal as proposal_service
from app.services.proposal import open_flags


def claim(text: str, status: str, **extra) -> dict:
    return {"text": text, "source_tag": "[F:abc12345]", "status": status, **extra}


# --- what counts as an open flag -----------------------------------------


def test_a_contradicted_claim_blocks_approval():
    assert open_flags([claim("turnover is 5 crore", "contradicted")]) == [
        "contradicted"
    ]


def test_an_unverifiable_claim_blocks_approval():
    assert open_flags([claim("we hold ISO 9001", "cannot_verify")]) == [
        "cannot_verify"
    ]


def test_a_verified_claim_never_blocked():
    assert open_flags([claim("turnover is 5 crore", "verified")]) == []


def test_a_resolved_claim_no_longer_blocks():
    """The regression this file exists for: before `resolution` existed, this
    section could never be approved by any action available to a user."""
    assert open_flags([
        claim("turnover is 5 crore", "contradicted",
              resolution="drop", resolved_by="Yuvraj"),
    ]) == []


def test_resolving_one_flag_leaves_the_others():
    flags = open_flags([
        claim("a", "contradicted", resolution="accept", resolved_by="Yuvraj"),
        claim("b", "contradicted"),
    ])
    assert flags == ["contradicted"]


# --- dropping a sentence edits the prose ----------------------------------


def test_dropping_removes_the_sentence_from_the_section():
    """Marking the claim resolved while leaving the prose would export a
    sentence the company cannot support — the opposite of the intent."""
    content = (
        "We are pleased to submit. Our turnover is 5 crore. "
        "We hold ISO 9001."
    )
    out = proposal_service._remove_sentence(content, "Our turnover is 5 crore.")

    assert "turnover" not in out
    assert "We are pleased to submit." in out
    assert "We hold ISO 9001." in out
    assert "  " not in out, "dropping mid-paragraph left a double space"


def test_removing_a_sentence_that_is_not_there_changes_nothing():
    content = "We hold ISO 9001."
    assert proposal_service._remove_sentence(content, "Our turnover is 5 crore.") == content


def test_remove_sentence_handles_empty_input():
    assert proposal_service._remove_sentence("", "anything") == ""
    assert proposal_service._remove_sentence("text", "") == "text"


# --- the guards on resolving ----------------------------------------------


def test_an_unknown_action_is_refused():
    refusal = proposal_service.validate_resolution("ignore", "Yuvraj", "")
    assert refusal is not None and "expected drop or accept" in refusal


def test_a_resolution_must_carry_a_name():
    """A checkpoint exists so that someone's name is against the decision."""
    refusal = proposal_service.validate_resolution("drop", "", "")
    assert refusal is not None and "name is required" in refusal


def test_accepting_a_flagged_claim_requires_a_written_reason():
    """Dropping is the safe action and needs no justification. Keeping a
    contradicted sentence in a bid document is the one that does."""
    refusal = proposal_service.validate_resolution("accept", "Yuvraj", "ok")
    assert refusal is not None and "written reason" in refusal


def test_dropping_needs_no_reason():
    assert proposal_service.validate_resolution("drop", "Yuvraj", "") is None


# --- approving a selection (US-11) ----------------------------------------


async def test_bulk_approval_needs_a_name():
    """One name covers the selection, but there still has to be one."""
    _, error = await proposal_service.approve_sections(None, None, ["s-1"], "")
    assert error is not None and "name is required" in error


async def test_bulk_approval_needs_a_selection():
    _, error = await proposal_service.approve_sections(None, None, [], "Yuvraj")
    assert error is not None and "no sections selected" in error


def test_accepting_with_a_real_reason_is_allowed():
    assert proposal_service.validate_resolution(
        "accept", "Yuvraj", "ISO cert renewed last week, not yet in the database"
    ) is None
