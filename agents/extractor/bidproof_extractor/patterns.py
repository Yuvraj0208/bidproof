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


# --- Reading a rule as a rule, not as a page ------------------------------
#
# requirement_text used to be the WHOLE matched element. A page-level block from
# the parser is the entire page, so a rule about the EMD arrived as "TENDER
# NOTICE No. 42/2026 Supply of industrial storage racks... Earnest Money..."
# — useless to a bid manager and useless in an export (FINISH_STATUS D7).
# The three helpers below narrow it to the clause, name the clause, and say
# whether it binds. All deterministic: no model touches any of this.

# Split on sentence ends and line breaks only. NOT on ":" — a colon sits INSIDE
# a tender clause ("Earnest Money Deposit: Rs 2,50,000"), and splitting there
# left requirement_text as the bare label with the figure stranded.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.;!?])\s+|\n+")

# "Clause 4.2", "Section 1", "Para 7(a)", "3.1.4" at the start of a line.
_CLAUSE_RE = re.compile(
    r"\b(?:clause|section|para(?:graph)?|annexure|schedule)\s+"
    r"([0-9]+(?:\.[0-9]+)*(?:\s*\([a-z0-9]+\))?|[ivxl]+)\b",
    re.IGNORECASE,
)
_NUMBERED_LINE_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+){1,3})\s+\S")

_MANDATORY_RE = re.compile(
    r"\b(?:must|shall|mandatory|required|compulsory|is\s+to\s+be)\b", re.IGNORECASE
)
_RECOMMENDED_RE = re.compile(r"\b(?:should|preferably|desirable)\b", re.IGNORECASE)
_OPTIONAL_RE = re.compile(r"\b(?:may|optional|at\s+the\s+discretion)\b", re.IGNORECASE)


def clause_sentence(text: str, start: int, end: int) -> str:
    """The sentence the match sits in, not the page it sits on."""
    pieces = []
    cursor = 0
    for piece in _SENTENCE_SPLIT_RE.split(text):
        if not piece:
            continue
        found = text.find(piece, cursor)
        if found == -1:
            found = cursor
        pieces.append((found, found + len(piece), piece))
        cursor = found + len(piece)
    for begin, finish, piece in pieces:
        if begin <= start < finish or (start < begin and end > begin):
            return piece.strip()
    return text.strip()[:500]


def clause_ref(text: str) -> str | None:
    """The tender's own reference for this clause, when it states one."""
    match = _CLAUSE_RE.search(text)
    if match:
        return match.group(0).strip()
    for line in text.splitlines():
        numbered = _NUMBERED_LINE_RE.match(line)
        if numbered:
            return numbered.group(1)
    return None


def obligation_of(text: str) -> str:
    """Does this bind the bidder? 'must/shall' binds; 'should' is preferred;
    'may' is optional. Anything unmarked is treated as mandatory — the safe
    reading for a tender, since assuming optional could lose the bid."""
    if _MANDATORY_RE.search(text):
        return "mandatory"
    if _RECOMMENDED_RE.search(text):
        return "recommended"
    if _OPTIONAL_RE.search(text):
        return "optional"
    return "mandatory"


def extract_pattern_rules(elements: list[ElementRef]) -> list[CandidateRule]:
    rules: list[CandidateRule] = []
    # Deduplicate on (key, value): a tender restates its terms on every page,
    # and the same requirement with the same figure is one rule, not five.
    # A DIFFERENT value under the same key is kept — that is a real conflict a
    # human needs to see, not noise to hide.
    seen: set[tuple[str, str | None]] = set()
    for element in elements:
        for family, key, pattern, group in _PATTERNS:
            match = pattern.search(element.text)
            if not match:
                continue
            value = match.group(group).strip()
            fingerprint = (key, normalize_numeric(value) or value.lower())
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            sentence = clause_sentence(element.text, match.start(), match.end())
            rules.append(
                CandidateRule(
                    family=family,
                    key=key,
                    requirement_text=sentence[:500],
                    value=value,
                    el_id=element.el_id,
                    source="pattern",
                    confidence=PATTERN_CONFIDENCE,
                    reason="exact value found by pattern",
                    clause_ref=clause_ref(element.text),
                    obligation=obligation_of(sentence),
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
