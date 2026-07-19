"""The gold-set evaluation harness (SPEC §12.1).

Runs the PURE pipeline (parse -> grounded elements -> extraction) over every
tender in tests/gold/ and scores it against the hand-labelled rules:

- precision / recall / F1 PER RULE FAMILY — never one blended number
- exact-match rate on numbers
- hallucination rate, re-verified against the elements (target: zero)
- the coverage-vs-accuracy curve (how thresholds get chosen, SPEC §12.1)

No DB, no network, no model — deterministic and CI-fast. The Model Lab
(US-14) reuses this harness with the AI side switched on.
"""

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from bidproof_extractor import ElementRef, extract_pattern_rules
from bidproof_extractor.patterns import normalize_numeric
from bidproof_parser import ParserLadder
from bidproof_parser.engines import PdfiumTextExtractor, UnavailableOcrEngine

GOLD_DIR = Path(__file__).parent / "gold"

COVERAGE_THRESHOLDS = [0.5, 0.6, 0.7, 0.8, 0.9, 0.95]


@dataclass
class FamilyScore:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0


@dataclass
class Report:
    tenders: int = 0
    families: dict = field(default_factory=lambda: defaultdict(FamilyScore))
    matched_keys: int = 0
    exact_values: int = 0
    hallucinations: int = 0
    predictions: list = field(default_factory=list)  # (confidence, correct)

    @property
    def exact_match_rate(self) -> float:
        return self.exact_values / self.matched_keys if self.matched_keys else 0.0

    @property
    def hallucination_rate(self) -> float:
        total = len(self.predictions)
        return self.hallucinations / total if total else 0.0

    def coverage_curve(self) -> list[dict]:
        curve = []
        total = len(self.predictions)
        for threshold in COVERAGE_THRESHOLDS:
            accepted = [(c, ok) for c, ok in self.predictions if c >= threshold]
            correct = sum(1 for _, ok in accepted if ok)
            curve.append(
                {
                    "threshold": threshold,
                    "coverage": round(len(accepted) / total, 3) if total else 0.0,
                    "accuracy": round(correct / len(accepted), 3) if accepted else None,
                }
            )
        return curve

    def to_dict(self) -> dict:
        return {
            "tenders": self.tenders,
            "per_family": {
                family: {
                    "precision": round(score.precision, 3),
                    "recall": round(score.recall, 3),
                    "f1": round(score.f1, 3),
                    "tp": score.tp,
                    "fp": score.fp,
                    "fn": score.fn,
                }
                for family, score in sorted(self.families.items())
            },
            "exact_number_match_rate": round(self.exact_match_rate, 3),
            "hallucination_rate": round(self.hallucination_rate, 4),
            "coverage_vs_accuracy": self.coverage_curve(),
        }


def _extract(pdf_bytes: bytes) -> tuple[list, dict]:
    ladder = ParserLadder(PdfiumTextExtractor(), UnavailableOcrEngine())
    result = ladder.parse(pdf_bytes)
    refs = [
        ElementRef(el_id=str(id(el)) + el.text[:8], page_no=el.page_no, text=el.text)
        for page in result.pages
        for el in page.elements
    ]
    return extract_pattern_rules(refs), {r.el_id: r for r in refs}


def evaluate(gold_dir: Path = GOLD_DIR) -> Report:
    report = Report()
    for folder in sorted(gold_dir.iterdir()):
        labels_path = folder / "labels.json"
        pdf_path = folder / "tender.pdf"
        if not labels_path.exists() or not pdf_path.exists():
            continue
        report.tenders += 1
        labels = json.loads(labels_path.read_text(encoding="utf-8"))

        predicted_rules, elements_by_id = _extract(pdf_path.read_bytes())
        predicted = {
            (r.family, r.key): (normalize_numeric(r.value), r)
            for r in predicted_rules
        }
        gold = {
            (g["family"], g["key"]): normalize_numeric(g["value"])
            for g in labels["rules"]
        }

        for (family, key), gold_value in gold.items():
            if (family, key) in predicted:
                predicted_value, rule = predicted[(family, key)]
                report.matched_keys += 1
                if predicted_value == gold_value:
                    report.families[family].tp += 1
                    report.exact_values += 1
                    report.predictions.append((rule.confidence, True))
                else:
                    report.families[family].fp += 1
                    report.families[family].fn += 1
                    report.predictions.append((rule.confidence, False))
            else:
                report.families[family].fn += 1

        for (family, key), (_, rule) in predicted.items():
            if (family, key) not in gold:
                report.families[family].fp += 1
                report.predictions.append((rule.confidence, False))
            # The hallucination check: the cited element must exist and must
            # actually contain the claimed digits (§9 rule 1, re-verified).
            element = elements_by_id.get(rule.el_id)
            claimed = normalize_numeric(rule.value)
            if element is None or (
                claimed and claimed not in (normalize_numeric(element.text) or "")
            ):
                report.hallucinations += 1

    return report
