"""A failed extraction must not destroy the rules a good one produced.

`extract_rules` replaces a document's rules by deleting them and inserting the
new set. That is correct when extraction worked. It is destructive when it did
not: if the model call fails, the pattern extractor may return nothing, and the
delete still runs — so a tender that had a full set of grounded rules is left
with none, and the console reports "0 rules" as though the document were empty.

Seen in practice on a real tender: three runs, the first extracting 11 rules
and the next two logging "model unavailable — pattern extraction only" and
leaving zero behind. The rules were not recoverable.

Losing good data to a transient outage is worse than doing nothing, so an
empty result over a document that already has rules is refused.
"""

from app.services import extraction


def test_empty_extraction_does_not_delete_existing_rules():
    """The regression: a model outage must not wipe a good rule set."""
    assert extraction._should_replace_rules(
        new_rule_count=0, existing_rule_count=11
    ) is False, (
        "an extraction that produced nothing would have deleted 11 good rules"
    )


def test_empty_extraction_is_fine_when_there_was_nothing_before():
    """No rules before and none now is not a loss — let it proceed."""
    assert extraction._should_replace_rules(
        new_rule_count=0, existing_rule_count=0
    ) is True


def test_a_successful_extraction_still_replaces():
    """The normal path must keep working: new rules replace old ones."""
    assert extraction._should_replace_rules(
        new_rule_count=14, existing_rule_count=11
    ) is True
    assert extraction._should_replace_rules(
        new_rule_count=1, existing_rule_count=0
    ) is True
