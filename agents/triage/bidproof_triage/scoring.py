"""The fit score and the two-list decision (SPEC §5.1).

Fit = w1·category + w2·provisional-eligibility + w3·value-band
    + w4·location + w5·win-history

Every component is deterministic. A component that cannot be evaluated is
None — it is excluded and the weights renormalise over what IS known, so
unknowns lower confidence instead of being guessed (§9 rule 3). If too
little is known, or the fit sits inside the borderline margin, the tender
queues for a human (Checkpoint 0)."""

from dataclasses import dataclass

from bidproof_triage.signals import days_to_close
from bidproof_triage.types import OrgProfile, TenderSignals, TriageResult

IN_OUR_LANE = "in_our_lane"
OPPORTUNITY_RADAR = "opportunity_radar"
NEEDS_HUMAN = "needs_human"
# Scored confidently, and it is simply not this company's work. Kept off
# the radar rather than deleted: the decision is auditable, and the tender
# is still reachable by asking for this list explicitly.
NOT_RELEVANT = "not_relevant"


@dataclass(frozen=True)
class Thresholds:
    in_lane: float = 0.55
    radar: float = 0.45
    confidence_floor: float = 0.5
    borderline_margin: float = 0.08


def _score_category(
    signals: TenderSignals, profile: OrgProfile
) -> tuple[float | None, str | None]:
    if not profile.categories:
        return None, None
    haystack = f"{signals.title} {signals.text}".lower()
    best_score, best_name = 0.0, None
    for category in profile.categories:
        if not category.keywords:
            continue
        hits = sum(1 for kw in category.keywords if kw.lower() in haystack)
        score = hits / len(category.keywords)
        if score > best_score:
            best_score, best_name = score, category.name
    return best_score, best_name


def _score_value(signals: TenderSignals, profile: OrgProfile) -> float | None:
    low, high = profile.value_band_inr
    if signals.value_inr is None or (low is None and high is None):
        return None
    if low is not None and signals.value_inr < low:
        return 0.0
    if high is not None and signals.value_inr > high:
        return 0.0
    return 1.0


def _score_location(signals: TenderSignals, profile: OrgProfile) -> float | None:
    if not profile.locations:
        return None
    haystack = f"{signals.title} {signals.text}".lower()
    return 1.0 if any(loc.lower() in haystack for loc in profile.locations) else None


def _score_eligibility(signals: TenderSignals, profile: OrgProfile) -> float | None:
    """Provisional only: quick checks evaluable from tender metadata. The
    real rule-by-rule check against the capability DB is Week-3 work."""
    passes, evaluable = 0, 0
    value_score = _score_value(signals, profile)
    if value_score is not None:
        evaluable += 1
        passes += int(value_score == 1.0)
    days = days_to_close(signals.closing_at, signals.now)
    if days is not None:
        evaluable += 1
        passes += int(days >= 0)
    if evaluable == 0:
        return None
    return passes / evaluable


def _inr_crore(value: float) -> str:
    return f"₹{value / 1e7:.2f} cr"


def triage(
    signals: TenderSignals,
    profile: OrgProfile,
    thresholds: Thresholds = Thresholds(),
) -> TriageResult:
    category_score, matched = _score_category(signals, profile)
    components: dict[str, float | None] = {
        "category": category_score,
        "eligibility": _score_eligibility(signals, profile),
        "value": _score_value(signals, profile),
        "location": _score_location(signals, profile),
        "win_history": (
            None
            if not matched
            else (1.0 if matched in profile.win_categories else 0.0)
        ),
    }

    total_weight = sum(profile.weights.values()) or 1.0
    known = {k: v for k, v in components.items() if v is not None}
    known_weight = sum(profile.weights.get(k, 0.0) for k in known)
    fit = (
        sum(profile.weights.get(k, 0.0) * v for k, v in known.items()) / known_weight
        if known_weight
        else 0.0
    )
    fit = round(fit, 3)
    coverage = round(known_weight / total_weight, 2)
    band = "green" if coverage >= 0.7 else "yellow" if coverage >= 0.4 else "red"

    reasons = _build_reasons(signals, profile, components, matched)

    deciding = thresholds.in_lane if matched else thresholds.radar
    if coverage < thresholds.confidence_floor:
        radar_list = NEEDS_HUMAN
        reasons.append(
            f"only {int(coverage * 100)}% of fit signals are known — queued for a human, not guessed"
        )
    elif abs(fit - deciding) < thresholds.borderline_margin:
        radar_list = NEEDS_HUMAN
        reasons.append(
            f"fit {fit:.2f} is borderline against the {deciding:.2f} threshold — queued for a human"
        )
    elif matched and fit >= thresholds.in_lane:
        radar_list = IN_OUR_LANE
    elif fit >= thresholds.radar:
        radar_list = OPPORTUNITY_RADAR
    else:
        # `thresholds.radar` used to be consulted only for the borderline check,
        # never to decide membership — so this branch was `else: OPPORTUNITY_RADAR`
        # and swept up everything. A PNB request for "suitable ready premises"
        # scored 0.10 and was presented as an opportunity Godrej could win. The
        # radar is supposed to be the tenders you COULD win but never bid on; a
        # list that also holds everything you could not is just noise.
        radar_list = NOT_RELEVANT
        reasons.append(
            f"fit {fit:.2f} is below the {thresholds.radar:.2f} relevance "
            "threshold — not shown on the radar"
        )

    checkpoint0 = (
        "auto_passed" if radar_list == IN_OUR_LANE and band == "green" else "queued"
    )
    return TriageResult(
        radar_list=radar_list,
        fit_score=fit,
        confidence=coverage,
        band=band,
        components=components,
        matched_category=matched,
        reasons=reasons,
        checkpoint0=checkpoint0,
    )


def _build_reasons(
    signals: TenderSignals,
    profile: OrgProfile,
    components: dict[str, float | None],
    matched: str | None,
) -> list[str]:
    reasons: list[str] = []

    if matched and components["category"]:
        reasons.append(
            f"category '{matched}' matched {int(components['category'] * 100)}%"
        )
    elif components["category"] is not None:
        reasons.append("no category match — outside current lanes")

    if signals.value_inr is None:
        reasons.append("tender value unknown")
    elif components["value"] is not None:
        low, high = profile.value_band_inr
        band_text = "within" if components["value"] == 1.0 else "outside"
        reasons.append(f"value {_inr_crore(signals.value_inr)} {band_text} the org band")

    days = days_to_close(signals.closing_at, signals.now)
    if days is None:
        reasons.append("closing date unknown")
    elif days < 0:
        reasons.append("closing date has passed")
    else:
        reasons.append(f"closes in {days} days")

    if components["win_history"] == 1.0:
        reasons.append("won in this category before")
    elif components["win_history"] == 0.0:
        reasons.append("never bid in this category")

    if components["location"] == 1.0:
        reasons.append("location matches an org location")

    if components["eligibility"] is not None:
        reasons.append(
            f"passes {int(components['eligibility'] * 100)}% of provisional checks"
        )
    return reasons
