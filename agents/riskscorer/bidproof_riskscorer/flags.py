"""Risk flags with rupee impacts (SPEC §5.5). Everything here is plain
arithmetic (§9 rule 2). A flag whose inputs are unknown is NOT emitted —
missing data never fabricates a risk, and never fabricates an all-clear
either; what we cannot price, the Bid Brief will show as unknown."""

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class RiskThresholds:
    pbg_max_percent: float = 5.0
    emd_max_percent_of_value: float = 2.0


@dataclass(frozen=True)
class RiskInputs:
    tender_value_inr: float | None
    closing_at: datetime | None
    now: datetime
    best_lead_time_days: int | None
    # rule-derived values (None when the rule was not extracted)
    pbg_percent: float | None = None
    pbg_el_id: str | None = None
    emd_amount_inr: float | None = None
    emd_el_id: str | None = None
    delivery_days: int | None = None
    delivery_el_id: str | None = None
    query_window_days: int | None = None
    query_el_id: str | None = None


@dataclass
class RiskFlag:
    code: str
    severity: str  # low | medium | high
    message: str
    rupee_impact: float | None
    el_id: str | None


def score_risks(inputs: RiskInputs, thresholds: RiskThresholds = RiskThresholds()
                ) -> list[RiskFlag]:
    flags: list[RiskFlag] = []

    if inputs.pbg_percent is not None and inputs.pbg_percent > thresholds.pbg_max_percent:
        impact = (
            round(inputs.pbg_percent / 100 * inputs.tender_value_inr, 2)
            if inputs.tender_value_inr is not None
            else None
        )
        flags.append(RiskFlag(
            code="pbg_too_high",
            severity="high" if inputs.pbg_percent >= 2 * thresholds.pbg_max_percent else "medium",
            message=f"PBG {inputs.pbg_percent:g}% exceeds the {thresholds.pbg_max_percent:g}% policy"
                    + (f" — ₹{impact / 1e5:.1f} lakh locked" if impact else ""),
            rupee_impact=impact,
            el_id=inputs.pbg_el_id,
        ))

    if inputs.emd_amount_inr is not None and inputs.tender_value_inr:
        emd_percent = inputs.emd_amount_inr / inputs.tender_value_inr * 100
        if emd_percent > thresholds.emd_max_percent_of_value:
            flags.append(RiskFlag(
                code="oversized_emd",
                severity="medium",
                message=f"EMD ₹{inputs.emd_amount_inr / 1e5:.1f} lakh is "
                        f"{emd_percent:.1f}% of tender value "
                        f"(policy cap {thresholds.emd_max_percent_of_value:g}%)",
                rupee_impact=round(inputs.emd_amount_inr, 2),
                el_id=inputs.emd_el_id,
            ))

    if (inputs.delivery_days is not None and inputs.best_lead_time_days is not None
            and inputs.delivery_days < inputs.best_lead_time_days):
        flags.append(RiskFlag(
            code="delivery_infeasible",
            severity="high",
            message=f"required delivery {inputs.delivery_days} days is shorter than "
                    f"our best lead time of {inputs.best_lead_time_days} days",
            rupee_impact=None,
            el_id=inputs.delivery_el_id,
        ))

    if (inputs.query_window_days is not None and inputs.closing_at is not None):
        query_deadline = inputs.closing_at - timedelta(days=inputs.query_window_days)
        if query_deadline < inputs.now:
            flags.append(RiskFlag(
                code="query_deadline_passed",
                severity="medium",
                message=f"the pre-bid query window closed on {query_deadline.date()} — "
                        "failed mandatory rules can no longer be challenged",
                rupee_impact=None,
                el_id=inputs.query_el_id,
            ))

    return flags
