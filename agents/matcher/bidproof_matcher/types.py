from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class Verdict(str, Enum):
    COMPLIES = "complies"
    PARTIAL = "partial"
    GAP = "gap"
    NOT_APPLICABLE = "not_applicable"
    NEEDS_HUMAN = "needs_human"


@dataclass(frozen=True)
class CheckRule:
    """The slice of a stored rule the matcher sees."""

    rule_id: str
    family: str
    key: str
    requirement_text: str
    value_text: str | None
    el_id: str


@dataclass(frozen=True)
class FactRef:
    id: str
    fact_type: str
    value_text: str | None = None
    value_number: float | None = None
    fiscal_year: str | None = None
    valid_until: date | None = None


@dataclass(frozen=True)
class ProductRef:
    id: str
    product_code: str
    product_name: str
    standards: tuple[str, ...] = ()
    lead_time_days: int | None = None
    specs: dict = field(default_factory=dict)


@dataclass
class VerdictResult:
    verdict: Verdict
    reason: str
    confidence: float
    arithmetic: bool
    cited_fact_id: str | None = None
    cited_product_id: str | None = None
