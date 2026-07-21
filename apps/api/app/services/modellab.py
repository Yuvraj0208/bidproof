"""The Model Comparison Lab (US-14, SPEC §12.4).

Runs the SAME gold set through N models for a role and produces a leaderboard:
F1 per family, exact-numbers, hallucination, citation-completeness, speed,
₹/tender. Because every model call already goes through the gateway roles,
adopting the winner is a config change (logged), not a code change.

Honesty (SPEC §20): with no API keys configured, the Lab runs clearly-labelled
SIMULATED model profiles — each perturbs the gold labels to a controlled
quality. The scoring is production-real; replacing a profile with a real
gateway is the same interface. Every row is marked `simulated: true`.
"""

import json
import random
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from app.core.db import org_scoped_session
from app.models import ModelLabRun

# apps/api/app/services/modellab.py -> repo root is five levels up.
_ROOT = Path(__file__).resolve().parents[4]
GOLD_DIR = _ROOT / "tests" / "gold"
# Model NAMES are config, not code (golden rule 7): loaded from infra, never
# hardcoded in application source.
PROFILES_PATH = _ROOT / "infra" / "model_profiles.json"


@dataclass(frozen=True)
class ModelProfile:
    name: str
    kind: str            # open | paid | baseline
    recall: float        # fraction of true rules the model recovers
    value_error: float   # fraction of recovered values it gets wrong
    fabrication: float   # chance of inventing an ungrounded rule per tender
    speed_ms: int
    cost_per_tender_inr: float


def load_profiles(role: str = "extraction") -> list[ModelProfile]:
    """Model names + quality stand-ins come from infra config, never code."""
    data = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
    return [
        ModelProfile(
            name=p["name"], kind=p["kind"], recall=p["recall"],
            value_error=p["value_error"], fabrication=p["fabrication"],
            speed_ms=p["speed_ms"], cost_per_tender_inr=p["cost_per_tender_inr"],
        )
        for p in data.get(role, data.get("extraction", []))
    ]


DEFAULT_PROFILES = load_profiles("extraction")

FAMILIES = ("eligibility", "technical", "commercial", "legal", "submission")


@dataclass
class _Tally:
    tp: int = 0
    fp: int = 0
    fn: int = 0


@dataclass
class _Scores:
    families: dict = field(default_factory=lambda: {f: _Tally() for f in FAMILIES})
    exact_matches: int = 0
    value_comparisons: int = 0
    fabricated: int = 0
    predicted_total: int = 0
    cited: int = 0


def _simulate(labels: list[dict], profile: ModelProfile, rng: random.Random,
              scores: _Scores) -> None:
    """Simulate one model's predictions for one tender and fold them into the
    running scores. A real gateway call would replace this function."""
    gold = {(g["family"], g["key"]): g.get("value") for g in labels}

    for (family, key), value in gold.items():
        recovered = rng.random() < profile.recall
        if not recovered:
            scores.families[family].fn += 1
            continue
        scores.families[family].tp += 1
        scores.predicted_total += 1
        scores.cited += 1  # recovered rules are grounded to a real element
        if value is not None:
            scores.value_comparisons += 1
            if rng.random() < profile.value_error:
                pass  # wrong value → not an exact match
            else:
                scores.exact_matches += 1

    # A fabrication is an ungrounded, invented rule — the ground-check would
    # discard it downstream, but the Lab counts it against the model.
    if rng.random() < profile.fabrication:
        scores.families["eligibility"].fp += 1
        scores.predicted_total += 1
        scores.fabricated += 1


def _row(profile: ModelProfile, scores: _Scores, tenders: int) -> dict:
    per_family = {}
    for family, tally in scores.families.items():
        p = tally.tp / (tally.tp + tally.fp) if (tally.tp + tally.fp) else 0.0
        r = tally.tp / (tally.tp + tally.fn) if (tally.tp + tally.fn) else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) else 0.0
        per_family[family] = round(f1, 3)
    overall_tp = sum(t.tp for t in scores.families.values())
    overall_fp = sum(t.fp for t in scores.families.values())
    overall_fn = sum(t.fn for t in scores.families.values())
    p = overall_tp / (overall_tp + overall_fp) if (overall_tp + overall_fp) else 0.0
    r = overall_tp / (overall_tp + overall_fn) if (overall_tp + overall_fn) else 0.0
    overall_f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return {
        "model": profile.name,
        "kind": profile.kind,
        "f1_overall": round(overall_f1, 3),
        "f1_eligibility": per_family["eligibility"],
        "f1_by_family": per_family,
        "exact_numbers": round(
            scores.exact_matches / scores.value_comparisons, 3
        ) if scores.value_comparisons else None,
        "hallucination_rate": round(
            scores.fabricated / scores.predicted_total, 4
        ) if scores.predicted_total else 0.0,
        "citation_complete": round(
            scores.cited / scores.predicted_total, 3
        ) if scores.predicted_total else 0.0,
        "speed_ms": profile.speed_ms,
        "cost_per_tender_inr": profile.cost_per_tender_inr,
        "simulated": True,
    }


def run_leaderboard(role: str = "extraction",
                    gold_dir: Path = GOLD_DIR,
                    profiles: list[ModelProfile] | None = None) -> dict:
    if profiles is None:
        profiles = load_profiles(role)
    tenders = [
        json.loads((p / "labels.json").read_text(encoding="utf-8"))
        for p in sorted(gold_dir.iterdir())
        if (p / "labels.json").exists()
    ]
    rows = []
    for profile in profiles:
        # Same gold set, same seed per model → reproducible, comparable.
        rng = random.Random(hash(profile.name) & 0xFFFFFFFF)
        scores = _Scores()
        for labels in tenders:
            _simulate(labels["rules"], profile, rng, scores)
        rows.append(_row(profile, scores, len(tenders)))
    rows.sort(key=lambda r: r["f1_overall"], reverse=True)
    return {"role": role, "gold_tenders": len(tenders), "simulated": True,
            "leaderboard": rows}


async def run_and_store(org_id: uuid.UUID, role: str = "extraction") -> dict:
    result = run_leaderboard(role)
    async with org_scoped_session(org_id) as session:
        session.add(ModelLabRun(
            org_id=org_id, role=role, gold_tenders=result["gold_tenders"],
            leaderboard=result["leaderboard"], simulated=True,
        ))
    return result
