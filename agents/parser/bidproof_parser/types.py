"""Typed shapes for the parser ladder.

Coordinate system: PDF points (1/72 inch), origin at the TOP-LEFT of the
page, y increasing downward — matching how pdf.js draws highlight boxes.
Engines that produce bottom-left coordinates must normalise before returning.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


class PageRoute(str, Enum):
    TEXT = "text"
    OCR = "ocr"


class PageStatus(str, Enum):
    PARSED = "parsed"
    FLAGGED = "flagged"


@dataclass(frozen=True)
class BBox:
    x0: float
    y0: float
    x1: float
    y1: float

    def is_valid(self) -> bool:
        return self.x1 > self.x0 and self.y1 > self.y0


@dataclass(frozen=True)
class RawElement:
    """What an engine returns. May be ungrounded — the ladder decides."""

    kind: str
    text: str
    bbox: BBox | None
    confidence: float | None


@dataclass(frozen=True)
class GroundedElement:
    """An element that passed the ground-check: it MUST have real text, a
    valid box, and a confidence. Nothing else leaves the parser."""

    kind: str
    text: str
    bbox: BBox
    confidence: float
    page_no: int
    seq: int


@dataclass(frozen=True)
class PageInfo:
    page_no: int
    width: float
    height: float
    char_count: int


@dataclass
class PageResult:
    page_no: int
    width: float
    height: float
    route: PageRoute
    status: PageStatus
    confidence: float
    elements: list[GroundedElement] = field(default_factory=list)
    discarded: int = 0  # engine outputs thrown away by the ground-check


@dataclass
class ParseResult:
    pages: list[PageResult]

    @property
    def pages_total(self) -> int:
        return len(self.pages)

    @property
    def pages_text(self) -> int:
        return sum(1 for p in self.pages if p.route is PageRoute.TEXT)

    @property
    def pages_ocr(self) -> int:
        return sum(1 for p in self.pages if p.route is PageRoute.OCR)

    @property
    def pages_flagged(self) -> int:
        return sum(1 for p in self.pages if p.status is PageStatus.FLAGGED)

    @property
    def needs_human(self) -> bool:
        return self.pages_flagged > 0

    @property
    def elements_discarded(self) -> int:
        return sum(p.discarded for p in self.pages)


class TextExtractor(Protocol):
    """Step 1: extract layout elements from pages that have a real text layer."""

    def extract(self, pdf_bytes: bytes, page_numbers: list[int]) -> dict[int, list[RawElement]]: ...


class OcrEngine(Protocol):
    """Step 2: OCR one page (the adapter rasterises at 300 dpi internally)."""

    def extract(self, pdf_bytes: bytes, page_no: int) -> list[RawElement]: ...
