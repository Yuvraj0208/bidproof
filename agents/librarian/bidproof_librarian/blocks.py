"""Chopping and retrieval of proposal blocks (SPEC §5.7).

Deterministic v1: headings split the document, keywords classify the
section, and retrieval ranks by outcome weight (won first) + keyword
overlap. The BGE-M3 hybrid upgrade slots in behind `rank_blocks` later.
"""

import re
from dataclasses import dataclass

SECTION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "cover_letter": ("cover", "letter", "introduction", "submission of bid"),
    "company_profile": ("about", "company", "profile", "organisation", "who we are"),
    "eligibility_compliance": ("eligibility", "qualification", "compliance",
                               "credentials"),
    "technical_approach": ("technical", "methodology", "approach",
                           "specification", "solution"),
    "delivery_and_support": ("delivery", "installation", "support", "warranty",
                             "after-sales"),
    "commercial_terms": ("commercial", "price", "payment", "terms", "taxes"),
    "declarations": ("declaration", "undertaking", "certificate", "annexure"),
}

_OUTCOME_WEIGHT = {"won": 2.0, "synthetic": 1.0, "lost": 0.5}

_HEADING_RE = re.compile(r"^(?:\d+[.)]\s*)?[A-Z][A-Za-z &/-]{2,60}:?\s*$")
_TOKEN_RE = re.compile(r"[a-z]{3,}")


@dataclass(frozen=True)
class LibraryBlock:
    section_tag: str
    text: str
    outcome: str          # won | lost | synthetic
    source_name: str


def classify_section(heading: str) -> str:
    lowered = heading.lower()
    best, hits = "company_profile", 0
    for tag, keywords in SECTION_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in lowered)
        if count > hits:
            best, hits = tag, count
    return best


def chop_proposal(text: str, outcome: str, source_name: str) -> list[LibraryBlock]:
    """Split on heading-like lines; each heading owns the paragraphs that
    follow it. A malformed document simply yields fewer blocks — never a
    guessed one."""
    blocks: list[LibraryBlock] = []
    heading: str | None = None
    body: list[str] = []

    def flush() -> None:
        content = "\n".join(body).strip()
        if heading and content:
            blocks.append(LibraryBlock(
                section_tag=classify_section(heading),
                text=content,
                outcome=outcome,
                source_name=source_name,
            ))

    for line in text.splitlines():
        if _HEADING_RE.match(line.strip()):
            flush()
            heading = line.strip()
            body = []
        else:
            body.append(line)
    flush()
    return blocks


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def rank_blocks(
    section_tag: str, context: str, blocks: list[LibraryBlock], top_k: int = 2
) -> list[LibraryBlock]:
    """Winning blocks first (SPEC §5.7): outcome weight dominates, keyword
    overlap with the tender context breaks ties."""
    wanted = _tokens(context)
    scored = []
    for block in blocks:
        if block.section_tag != section_tag:
            continue
        overlap = len(wanted & _tokens(block.text))
        score = _OUTCOME_WEIGHT.get(block.outcome, 0.0) * 100 + overlap
        scored.append((score, block))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [block for _, block in scored[:top_k]]
