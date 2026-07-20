"""Claim verification (SPEC §5.7). Deterministic v1: a claim's number tokens
must all appear in its cited fact's text. Numbers are compared by code,
never by a model (§9 rule 2)."""

import re
from dataclasses import dataclass

TAG_RE = re.compile(r"\[(?:F|P):[0-9a-f]{8}\]")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_NUMBER_TOKEN_RE = re.compile(r"\d+(?:\.\d+)?")

VERIFIED = "verified"
CANNOT_VERIFY = "cannot_verify"
CONTRADICTED = "contradicted"


@dataclass(frozen=True)
class Claim:
    text: str
    source_tag: str | None
    status: str


def _number_tokens(text: str) -> list[str]:
    return _NUMBER_TOKEN_RE.findall(text.replace(",", ""))


def _merge_tag_fragments(parts: list[str]) -> list[str]:
    """Tags follow the period ("... crore. [F:x]"), so a naive sentence split
    orphans them. Re-attach any fragment that is only tags to its sentence."""
    merged: list[str] = []
    for part in parts:
        if merged and not TAG_RE.sub("", part).strip(" .!?"):
            merged[-1] = f"{merged[-1]} {part.strip()}"
        else:
            merged.append(part)
    return merged


def _sentences(text: str) -> list[str]:
    out: list[str] = []
    for line in text.splitlines():
        parts = [s.strip() for s in _SENTENCE_SPLIT_RE.split(line) if s.strip()]
        out.extend(_merge_tag_fragments(parts))
    return out


def check_text(
    text: str, facts_by_tag: dict[str, str], ignore_context: tuple[str, ...] = ()
) -> list[Claim]:
    """`ignore_context` holds quoted tender context (e.g. the tender's own
    title/reference number): its digits are the buyer's words, not a company
    claim, so a sentence that only restates them is not a claim."""
    claims: list[Claim] = []
    for sentence in _sentences(text):
        tags = TAG_RE.findall(sentence)
        stripped = TAG_RE.sub("", sentence)
        for context in ignore_context:
            stripped = stripped.replace(context, "")
        numbers = _number_tokens(stripped)
        if not tags and not numbers:
            continue  # style, not a claim

        if not tags:
            claims.append(Claim(sentence, None, CANNOT_VERIFY))
            continue

        tag = tags[0]
        fact = facts_by_tag.get(tag)
        if fact is None:
            claims.append(Claim(sentence, tag, CANNOT_VERIFY))
            continue

        fact_numbers = set(_number_tokens(fact))
        if all(token in fact_numbers for token in numbers):
            claims.append(Claim(sentence, tag, VERIFIED))
        else:
            claims.append(Claim(sentence, tag, CONTRADICTED))
    return claims


def verified_percentage(claims: list[Claim]) -> float | None:
    """None when a section makes no claims at all — 'no claims' is honest,
    a fake 100% is not."""
    if not claims:
        return None
    verified = sum(1 for c in claims if c.status == VERIFIED)
    return round(100 * verified / len(claims), 1)
