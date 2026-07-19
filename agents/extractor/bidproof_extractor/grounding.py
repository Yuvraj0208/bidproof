"""The ground-check and the dual-extractor comparison (SPEC §5.3).

Ground-check (§9 rule 1, doubling as the anti-injection filter §11.1):
a rule citing an element that does not exist, or carrying a value its cited
element does not actually contain, is THROWN AWAY and counted — never
down-scored, never repaired.
"""

from bidproof_extractor.patterns import normalize_numeric
from bidproof_extractor.schema import AiRule
from bidproof_extractor.types import CandidateRule, ElementRef

CONF_BOTH_AGREE = 0.97
CONF_PATTERN_ONLY = 0.9
CONF_AI_ONLY = 0.75
CONF_VOTE_RESOLVED = 0.85
CONF_NEEDS_HUMAN = 0.4


def ground_check(
    ai_rules: list[AiRule], elements_by_id: dict[str, ElementRef]
) -> tuple[list[CandidateRule], int]:
    """Every AI rule must point at a real element, and any digits it claims
    must literally appear in that element's text."""
    kept: list[CandidateRule] = []
    discarded = 0
    for rule in ai_rules:
        element = elements_by_id.get(rule.el_id)
        if element is None:
            discarded += 1
            continue
        claimed = normalize_numeric(rule.value)
        if claimed is not None:
            element_digits = normalize_numeric(element.text) or ""
            if claimed not in element_digits:
                discarded += 1
                continue
        kept.append(
            CandidateRule(
                family=rule.family,
                key=rule.key,
                requirement_text=rule.requirement_text.strip()[:500],
                value=rule.value,
                el_id=rule.el_id,
                source="ai",
                confidence=CONF_AI_ONLY,
                reason="model extraction, grounded to its cited element",
            )
        )
    return kept, discarded


def compare_and_merge(
    pattern_rules: list[CandidateRule], ai_rules: list[CandidateRule]
) -> tuple[list[CandidateRule], list[tuple[CandidateRule, CandidateRule]]]:
    """Merge the two sides by key. Agreement raises confidence; numeric
    disagreement is returned for the 3x vote. Comparison is plain string /
    digit normalisation — never a model (§9 rule 2)."""
    ai_by_key = {r.key: r for r in ai_rules}
    merged: list[CandidateRule] = []
    disputes: list[tuple[CandidateRule, CandidateRule]] = []

    for rule in pattern_rules:
        twin = ai_by_key.pop(rule.key, None)
        if twin is None:
            merged.append(rule)
            continue
        if normalize_numeric(rule.value) == normalize_numeric(twin.value):
            rule.source = "both"
            rule.confidence = CONF_BOTH_AGREE
            rule.reason = "pattern and model agree on the exact value"
            merged.append(rule)
        else:
            disputes.append((rule, twin))

    merged.extend(ai_by_key.values())
    return merged, disputes


def resolve_vote(
    pattern_rule: CandidateRule, vote_values: list[str | None]
) -> CandidateRule:
    """The model voted 3x on a disputed value. Majority matching the pattern
    resolves it; anything else goes to a human (§9 rule 3). The pattern's
    grounded citation is kept either way — the value in question is the one
    the regex physically found on the page."""
    pattern_norm = normalize_numeric(pattern_rule.value)
    agreeing = sum(1 for v in vote_values if normalize_numeric(v) == pattern_norm)
    if agreeing >= 2:
        pattern_rule.source = "vote"
        pattern_rule.confidence = CONF_VOTE_RESOLVED
        pattern_rule.reason = f"disagreement resolved: {agreeing}/3 votes match the pattern value"
    else:
        pattern_rule.status = "needs_human"
        pattern_rule.confidence = CONF_NEEDS_HUMAN
        pattern_rule.reason = "pattern and model still disagree after 3 votes — a human decides"
    return pattern_rule
