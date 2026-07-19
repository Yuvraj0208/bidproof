"""Candidate retrieval for spec-match rules.

Default: deterministic keyword overlap — honest, fast, zero dependencies.
The BGE-M3 hybrid + bge-reranker upgrade (SPEC §5.5) slots in behind this
same interface as a heavy optional install, exactly like Docling did for
parsing. Swapping it in changes retrieval quality, never the contract.
"""

import re
from typing import Protocol

from bidproof_matcher.types import ProductRef

_TOKEN_RE = re.compile(r"[a-z0-9]{3,}")

_STOPWORDS = {
    "the", "and", "for", "with", "shall", "must", "should", "bidder",
    "supplier", "tender", "all", "any", "per", "from", "will", "have",
}


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(text.lower())} - _STOPWORDS


class CandidateRetriever(Protocol):
    def retrieve(self, rule_text: str, products: list[ProductRef], top_k: int = 3
                 ) -> list[ProductRef]: ...


class KeywordRetriever:
    def retrieve(self, rule_text: str, products: list[ProductRef], top_k: int = 3
                 ) -> list[ProductRef]:
        wanted = _tokens(rule_text)
        if not wanted:
            return []
        scored = []
        for product in products:
            haystack = _tokens(
                f"{product.product_name} {product.product_code} "
                + " ".join(product.standards)
                + " " + " ".join(str(v) for v in product.specs.values())
            )
            overlap = len(wanted & haystack)
            if overlap:
                scored.append((overlap, product))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [product for _, product in scored[:top_k]]
