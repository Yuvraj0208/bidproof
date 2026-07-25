from dataclasses import dataclass

FAMILIES = ("eligibility", "technical", "commercial", "legal", "submission")


@dataclass(frozen=True)
class ElementRef:
    """The slice of a grounded element the extractor is allowed to see."""

    el_id: str
    page_no: int
    text: str


@dataclass
class CandidateRule:
    family: str
    key: str
    requirement_text: str
    value: str | None
    el_id: str
    source: str            # pattern | ai | both | vote
    status: str = "extracted"   # extracted | needs_human
    confidence: float = 0.0
    reason: str = ""
    # The tender's own reference for this clause ("Clause 4.2"), when stated.
    clause_ref: str | None = None
    # Does it bind the bidder? mandatory | recommended | optional.
    obligation: str = "mandatory"
