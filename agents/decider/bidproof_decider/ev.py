"""The bid decision (SPEC §5.6). All money maths is plain code (§9 rule 2).

1. Hard gate: fail any mandatory eligibility rule -> NO.
2. EV = P(win) x profit - cost of bidding
       (man-days x loaded day rate + cost of money locked in EMD/PBG).
3. Unknown tender value -> NEEDS_HUMAN, never a guessed EV (§9 rule 3).

The output shows every term with its formula — a rupee figure a CFO can
argue with, not a score out of ten.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EvConfig:
    """Config weights (SPEC §5.6 step 2) — sponsor-validated, never hardcoded
    at call sites. Defaults are the pilot's starting assumptions (§16)."""

    p_win: float = 0.3
    profit_margin_percent: float = 10.0
    man_days: float = 12.0
    loaded_day_rate_inr: float = 15000.0
    capital_rate_annual: float = 0.12
    lock_months: float = 6.0


@dataclass
class DecisionOutcome:
    recommendation: str          # go | no_go | needs_human
    ev_inr: float | None
    terms: list[dict] = field(default_factory=list)
    gate_failed: list[dict] = field(default_factory=list)
    confidence: float = 0.0
    reason: str = ""


def hard_gate(verdicts: list[dict]) -> list[dict]:
    """Mandatory eligibility rules that FAILED. Any entry here means NO,
    whatever the EV says."""
    return [
        v for v in verdicts
        if v.get("family") == "eligibility" and v.get("verdict") == "gap"
    ]


def _lakh(value: float) -> str:
    return f"₹{value / 1e5:.2f} lakh"


def decide(
    verdicts: list[dict],
    tender_value_inr: float | None,
    emd_inr: float | None,
    pbg_percent: float | None,
    config: EvConfig = EvConfig(),
) -> DecisionOutcome:
    failed = hard_gate(verdicts)
    if failed:
        keys = ", ".join(v.get("key", "?") for v in failed)
        return DecisionOutcome(
            recommendation="no_go",
            ev_inr=None,
            gate_failed=failed,
            confidence=0.95,
            reason=f"hard gate: mandatory eligibility failed ({keys}) — "
                   "EV not computed; a human may override with a written reason",
        )

    if tender_value_inr is None:
        return DecisionOutcome(
            recommendation="needs_human",
            ev_inr=None,
            confidence=0.3,
            reason="tender value unknown — EV cannot be computed honestly; "
                   "enter the value in the Decision Room",
        )

    profit = config.profit_margin_percent / 100 * tender_value_inr
    expected_profit = config.p_win * profit
    bid_effort = config.man_days * config.loaded_day_rate_inr
    locked_amount = (emd_inr or 0.0) + (pbg_percent or 0.0) / 100 * tender_value_inr
    locked_cost = locked_amount * config.capital_rate_annual * config.lock_months / 12
    ev = round(expected_profit - bid_effort - locked_cost, 2)

    terms = [
        {"key": "expected_profit",
         "label": "Expected profit",
         "formula": f"P(win) {config.p_win:.0%} × margin "
                    f"{config.profit_margin_percent:g}% × value {_lakh(tender_value_inr)}",
         "value_inr": round(expected_profit, 2)},
        {"key": "bid_effort",
         "label": "Cost of bidding (effort)",
         "formula": f"{config.man_days:g} man-days × ₹{config.loaded_day_rate_inr:,.0f}/day",
         "value_inr": round(-bid_effort, 2)},
        {"key": "locked_capital",
         "label": "Cost of locked money (EMD + PBG)",
         "formula": f"{_lakh(locked_amount)} locked × {config.capital_rate_annual:.0%} "
                    f"p.a. × {config.lock_months:g}/12 months",
         "value_inr": round(-locked_cost, 2)},
    ]

    # Confidence in the recommendation itself: how much of the money picture
    # was known vs defaulted (§9 rule 8).
    known = sum(1 for x in (emd_inr, pbg_percent) if x is not None)
    confidence = round(0.6 + 0.15 * known, 2)

    return DecisionOutcome(
        recommendation="go" if ev > 0 else "no_go",
        ev_inr=ev,
        terms=terms,
        confidence=confidence,
        reason=f"EV {_lakh(ev)} — " + ("positive: bid" if ev > 0 else "negative: do not bid"),
    )
