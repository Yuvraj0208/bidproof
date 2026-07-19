from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Category:
    name: str
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class OrgProfile:
    """Per-tenant triage configuration (SPEC §15). Weights are config —
    never hardcoded — and the sponsor validates them (SPEC §16)."""

    categories: tuple[Category, ...] = ()
    weights: dict[str, float] = field(
        default_factory=lambda: {
            "category": 0.35,
            "eligibility": 0.25,
            "value": 0.15,
            "location": 0.10,
            "win_history": 0.15,
        }
    )
    value_band_inr: tuple[float | None, float | None] = (None, None)
    locations: tuple[str, ...] = ()
    win_categories: tuple[str, ...] = ()


@dataclass(frozen=True)
class TenderSignals:
    title: str
    text: str
    value_inr: float | None
    closing_at: datetime | None
    now: datetime


@dataclass
class TriageResult:
    radar_list: str          # in_our_lane | opportunity_radar | needs_human
    fit_score: float
    confidence: float
    band: str                # green | yellow | red
    components: dict[str, float | None]
    matched_category: str | None
    reasons: list[str]
    checkpoint0: str         # auto_passed | queued
