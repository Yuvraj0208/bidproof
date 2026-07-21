"""Injection / jailbreak screening (SPEC §10, §11).

Deterministic pattern rules now; a small guard classifier layers on behind
the same `scan` interface later. A flagged input is treated as inert data —
it never becomes an instruction.
"""

import re
from dataclasses import dataclass

# Each rule: (category, compiled pattern). Kept readable and extendable — the
# attack suite (US-19) grows this set with every neutralised attack.
_RULES: list[tuple[str, re.Pattern]] = [
    ("prompt_injection", re.compile(
        r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions", re.I)),
    ("prompt_injection", re.compile(r"disregard\s+(?:all\s+)?(?:previous|prior|the above)", re.I)),
    ("prompt_injection", re.compile(r"\bsystem\s*[:>]", re.I)),
    ("role_override", re.compile(r"you\s+are\s+now\s+(?:a|an|the)\b", re.I)),
    ("role_override", re.compile(r"\bpretend\s+(?:to\s+be|you\s+are)\b", re.I)),
    ("role_override", re.compile(r"\bact\s+as\s+(?:a|an|if)\b", re.I)),
    ("jailbreak", re.compile(r"\bjailbreak\b", re.I)),
    ("jailbreak", re.compile(r"\bDAN\b")),
    ("prompt_leak", re.compile(r"(?:reveal|show|print|repeat)\s+(?:your\s+)?"
                               r"(?:system\s+)?prompt", re.I)),
    ("verdict_tampering", re.compile(
        r"mark\s+(?:everything|all|every\s+\w+)\s+(?:as\s+)?(?:complies|compliant|pass)", re.I)),
    ("verdict_tampering", re.compile(r"set\s+(?:the\s+)?(?:expected\s+value|ev)\s+to", re.I)),
]


@dataclass(frozen=True)
class GuardVerdict:
    flagged: bool
    category: str | None = None
    matched: str | None = None


def scan(text: str) -> GuardVerdict:
    if not text:
        return GuardVerdict(flagged=False)
    for category, pattern in _RULES:
        match = pattern.search(text)
        if match:
            return GuardVerdict(flagged=True, category=category,
                                matched=match.group(0)[:100])
    return GuardVerdict(flagged=False)
