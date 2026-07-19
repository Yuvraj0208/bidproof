"""The pattern extractor: regex for anything exact. An AI never guesses a
number a regex can find (§9 rule 2). Every hit cites the element it matched
in — grounding is intrinsic here, not checked after the fact."""

import re

from bidproof_extractor.types import CandidateRule, ElementRef

PATTERN_CONFIDENCE = 0.9

# (family, key, compiled regex, which group is the value)
_PATTERNS: list[tuple[str, str, re.Pattern, int]] = [
    (
        "commercial",
        "emd_amount",
        re.compile(
            r"(?:emd|earnest\s+money(?:\s+deposit)?)\D{0,30}?((?:₹|rs\.?|inr)\s*[\d,]+(?:\.\d+)?(?:\s*(?:crore|cr|lakh|lacs?))?)",
            re.IGNORECASE,
        ),
        1,
    ),
    (
        "eligibility",
        "min_turnover",
        re.compile(
            r"turnover\D{0,40}?((?:₹|rs\.?|inr)\s*[\d,]+(?:\.\d+)?\s*(?:crore|cr|lakh|lacs?)?)",
            re.IGNORECASE,
        ),
        1,
    ),
    (
        "commercial",
        "delivery_days",
        re.compile(r"delivery(?:\s+period)?\D{0,20}?(\d{1,4})\s*days", re.IGNORECASE),
        1,
    ),
    (
        "commercial",
        "pbg_percent",
        re.compile(
            r"(?:performance\s+bank\s+guarantee|pbg)\D{0,20}?([\d.]{1,6})\s*(?:%|percent)",
            re.IGNORECASE,
        ),
        1,
    ),
    (
        "technical",
        "required_standard",
        re.compile(r"\b(iso\s*\d{4,5}(?::\d{4})?)\b", re.IGNORECASE),
        1,
    ),
    (
        "submission",
        "prebid_query_window_days",
        re.compile(
            r"(?:pre-?bid\s+)?quer(?:y|ies)\D{0,30}?(\d{1,3})\s*days", re.IGNORECASE
        ),
        1,
    ),
]


def extract_pattern_rules(elements: list[ElementRef]) -> list[CandidateRule]:
    rules: list[CandidateRule] = []
    seen: set[tuple[str, str]] = set()
    for element in elements:
        for family, key, pattern, group in _PATTERNS:
            match = pattern.search(element.text)
            if not match:
                continue
            if (key, element.el_id) in seen:
                continue
            seen.add((key, element.el_id))
            rules.append(
                CandidateRule(
                    family=family,
                    key=key,
                    requirement_text=element.text.strip()[:500],
                    value=match.group(group).strip(),
                    el_id=element.el_id,
                    source="pattern",
                    confidence=PATTERN_CONFIDENCE,
                    reason="exact value found by pattern",
                )
            )
    return rules


_NUM_RE = re.compile(r"[\d.]+")


def normalize_numeric(value: str | None) -> str | None:
    """Digits-only normal form for comparing two extractors' values.
    Plain string handling — no model ever touches a number (§9 rule 2)."""
    if value is None:
        return None
    digits = "".join(_NUM_RE.findall(value.replace(",", "")))
    return digits or None
