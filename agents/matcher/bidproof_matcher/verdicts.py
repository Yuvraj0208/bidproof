"""Arithmetic verdicts (§9 rule 2): numbers are compared by code, never by a
model. Note the signatures — no gateway, no client, no model handle exists
in this module, so an LLM call is structurally impossible here.

Abstention is success (§9 rule 3): missing capability data yields
NEEDS_HUMAN, never an assumed pass.
"""

import re
from datetime import date

from bidproof_matcher.types import (
    CheckRule,
    FactRef,
    ProductRef,
    Verdict,
    VerdictResult,
)

CONF_ARITHMETIC = 0.95
CONF_PARTIAL = 0.8
CONF_NEEDS_HUMAN = 0.4

_INR_RE = re.compile(
    r"(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)\s*(crore|cr|lakh|lacs?)?", re.IGNORECASE
)
_MULTIPLIERS = {None: 1.0, "cr": 1e7, "crore": 1e7, "lakh": 1e5, "lac": 1e5, "lacs": 1e5}


def parse_inr(value: str | None) -> float | None:
    """One labelled amount string -> rupees. Deterministic; None when the
    string does not parse — never a guess."""
    if not value:
        return None
    match = _INR_RE.search(value)
    if not match:
        return None
    try:
        amount = float(match.group(1).replace(",", ""))
    except ValueError:
        return None
    unit = (match.group(2) or "").lower() or None
    return amount * _MULTIPLIERS.get(unit, 1.0)


def _check_min_turnover(rule: CheckRule, facts: list[FactRef], _: list[ProductRef],
                        today: date) -> VerdictResult:
    required = parse_inr(rule.value_text)
    if required is None:
        return VerdictResult(Verdict.NEEDS_HUMAN, "turnover requirement did not parse",
                             CONF_NEEDS_HUMAN, arithmetic=True)
    turnovers = [f for f in facts if f.fact_type == "turnover" and f.value_number is not None]
    if not turnovers:
        return VerdictResult(Verdict.NEEDS_HUMAN,
                             "no verified turnover facts on file",
                             CONF_NEEDS_HUMAN, arithmetic=True)
    recent = sorted(turnovers, key=lambda f: f.fiscal_year or "", reverse=True)[:3]
    average = sum(f.value_number for f in recent) / len(recent)
    cited = recent[0].id
    if average >= required:
        return VerdictResult(
            Verdict.COMPLIES,
            f"average turnover over {len(recent)} FY is ₹{average / 1e7:.2f} cr "
            f"vs required ₹{required / 1e7:.2f} cr",
            CONF_ARITHMETIC, arithmetic=True, cited_fact_id=cited)
    return VerdictResult(
        Verdict.GAP,
        f"average turnover ₹{average / 1e7:.2f} cr is below the required "
        f"₹{required / 1e7:.2f} cr",
        CONF_ARITHMETIC, arithmetic=True, cited_fact_id=cited)


def _check_delivery(rule: CheckRule, _: list[FactRef], products: list[ProductRef],
                    today: date) -> VerdictResult:
    try:
        required = int(rule.value_text or "")
    except ValueError:
        return VerdictResult(Verdict.NEEDS_HUMAN, "delivery requirement did not parse",
                             CONF_NEEDS_HUMAN, arithmetic=True)
    with_lead = [p for p in products if p.lead_time_days is not None]
    if not with_lead:
        return VerdictResult(Verdict.NEEDS_HUMAN,
                             "no catalogue lead times on file",
                             CONF_NEEDS_HUMAN, arithmetic=True)
    best = min(with_lead, key=lambda p: p.lead_time_days)
    if best.lead_time_days <= required:
        return VerdictResult(
            Verdict.COMPLIES,
            f"{best.product_name} ships in {best.lead_time_days} days vs "
            f"{required} required",
            CONF_ARITHMETIC, arithmetic=True, cited_product_id=best.id)
    return VerdictResult(
        Verdict.GAP,
        f"best lead time is {best.lead_time_days} days vs {required} required",
        CONF_ARITHMETIC, arithmetic=True, cited_product_id=best.id)


def _normalise_standard(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower().split(":")[0])


def _check_standard(rule: CheckRule, facts: list[FactRef], products: list[ProductRef],
                    today: date) -> VerdictResult:
    wanted = _normalise_standard(rule.value_text or "")
    if not wanted:
        return VerdictResult(Verdict.NEEDS_HUMAN, "standard requirement did not parse",
                             CONF_NEEDS_HUMAN, arithmetic=True)
    certs = [f for f in facts if f.fact_type == "certification" and f.value_text]
    for cert in certs:
        if wanted in _normalise_standard(cert.value_text):
            if cert.valid_until is None or cert.valid_until >= today:
                return VerdictResult(
                    Verdict.COMPLIES,
                    f"certified: {cert.value_text}"
                    + (f", valid until {cert.valid_until}" if cert.valid_until else ""),
                    CONF_ARITHMETIC, arithmetic=True, cited_fact_id=cert.id)
            return VerdictResult(
                Verdict.PARTIAL,
                f"{cert.value_text} expired on {cert.valid_until} — renewal needed",
                CONF_PARTIAL, arithmetic=True, cited_fact_id=cert.id)
    for product in products:
        if any(wanted in _normalise_standard(s) for s in product.standards):
            return VerdictResult(
                Verdict.PARTIAL,
                f"{product.product_name} meets the standard, but no company "
                "certificate is on file",
                CONF_PARTIAL, arithmetic=True, cited_product_id=product.id)
    return VerdictResult(
        Verdict.GAP,
        f"no certificate or product covers {rule.value_text}",
        CONF_ARITHMETIC, arithmetic=True)


def _commercial_term(rule: CheckRule, *_args) -> VerdictResult:
    return VerdictResult(
        Verdict.NOT_APPLICABLE,
        "commercial/submission term — priced in the EV and risk-scored, "
        "not matched against capability",
        CONF_ARITHMETIC, arithmetic=True)


ARITHMETIC_KEYS = {
    "min_turnover": _check_min_turnover,
    "delivery_days": _check_delivery,
    "required_standard": _check_standard,
    "emd_amount": _commercial_term,
    "pbg_percent": _commercial_term,
    "prebid_query_window_days": _commercial_term,
}


def check_rule(rule: CheckRule, facts: list[FactRef], products: list[ProductRef],
               today: date) -> VerdictResult | None:
    """Arithmetic path. Returns None for keys this module cannot decide —
    those go to the retriever + cited judge, or to a human."""
    checker = ARITHMETIC_KEYS.get(rule.key)
    if checker is None:
        return None
    return checker(rule, facts, products, today)
