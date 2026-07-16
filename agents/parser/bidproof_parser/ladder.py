"""The 4-step reader ladder (SPEC §5.2), cheapest step first.

Step 0  pypdfium2: does the page have a real text layer, or is it a picture?
Step 1  real text  -> TextExtractor (Docling in production).
Step 2  scan/wrong -> OcrEngine (PaddleOCR-VL in production, 300 dpi).
Step 3  still wrong -> the page is FLAGGED for a human. Never guess.

The ground-check runs on every engine output: an element without real text,
a valid box, and a confidence is discarded and counted — it does not exist.
"""

import string

import pypdfium2 as pdfium

from bidproof_parser.types import (
    GroundedElement,
    OcrEngine,
    PageInfo,
    PageResult,
    PageRoute,
    PageStatus,
    ParseResult,
    RawElement,
    TextExtractor,
)

_PLAUSIBLE_CHARS = set(
    string.ascii_letters + string.digits + string.punctuation + " "
)


def inspect_pages(pdf_bytes: bytes) -> list[PageInfo]:
    """Step 0: page dimensions + how many text-layer characters each page has."""
    pdf = pdfium.PdfDocument(pdf_bytes)
    try:
        infos = []
        for index in range(len(pdf)):
            page = pdf[index]
            width, height = page.get_size()
            textpage = page.get_textpage()
            infos.append(
                PageInfo(
                    page_no=index + 1,
                    width=width,
                    height=height,
                    char_count=textpage.count_chars(),
                )
            )
            textpage.close()
            page.close()
        return infos
    finally:
        pdf.close()


def looks_like_garbage(elements: list[RawElement]) -> bool:
    """A text page whose extraction is empty or mostly implausible characters
    is treated as wrong and re-routed to OCR (broken encodings, exotic CID
    fonts, mangled scans with a fake text layer)."""
    text = " ".join(e.text for e in elements if e.text)
    stripped = text.strip()
    if not stripped:
        return True
    # Devanagari and other non-Latin scripts are NOT garbage; only flag when
    # the bulk of characters are neither plausible ASCII nor letters at all.
    plausible = sum(1 for ch in stripped if ch in _PLAUSIBLE_CHARS or ch.isalpha())
    return plausible / len(stripped) < 0.5


def compute_parse_cost_inr(pages_ocr: int, ocr_cost_per_page_inr: float) -> float:
    """Rupee cost of a parse run. Plain arithmetic — never a model (§9 rule 2).
    Local engines cost 0; the rate becomes real if OCR moves to a hosted GPU."""
    return round(pages_ocr * ocr_cost_per_page_inr, 4)


class ParserLadder:
    def __init__(
        self,
        text_extractor: TextExtractor,
        ocr_engine: OcrEngine,
        *,
        min_chars_text_page: int = 25,
        page_confidence_threshold: float = 0.6,
    ) -> None:
        self._text_extractor = text_extractor
        self._ocr_engine = ocr_engine
        self._min_chars = min_chars_text_page
        self._conf_threshold = page_confidence_threshold

    def parse(self, pdf_bytes: bytes) -> ParseResult:
        infos = inspect_pages(pdf_bytes)

        routes: dict[int, PageRoute] = {
            info.page_no: (
                PageRoute.TEXT if info.char_count >= self._min_chars else PageRoute.OCR
            )
            for info in infos
        }

        text_pages = [n for n, r in routes.items() if r is PageRoute.TEXT]
        extracted: dict[int, list[RawElement]] = (
            self._text_extractor.extract(pdf_bytes, text_pages) if text_pages else {}
        )

        # Step 2 rerouting: a "text" page whose extraction looks wrong gets
        # one honest retry through OCR before anyone gives up on it.
        for page_no in text_pages:
            if looks_like_garbage(extracted.get(page_no, [])):
                routes[page_no] = PageRoute.OCR

        pages: list[PageResult] = []
        for info in infos:
            route = routes[info.page_no]
            if route is PageRoute.OCR:
                raw = self._ocr_engine.extract(pdf_bytes, info.page_no)
            else:
                raw = extracted.get(info.page_no, [])

            grounded, discarded = self._ground(raw, info.page_no)
            confidence = min((e.confidence for e in grounded), default=0.0)
            flagged = not grounded or confidence < self._conf_threshold
            pages.append(
                PageResult(
                    page_no=info.page_no,
                    width=info.width,
                    height=info.height,
                    route=route,
                    status=PageStatus.FLAGGED if flagged else PageStatus.PARSED,
                    confidence=confidence,
                    elements=grounded,
                    discarded=discarded,
                )
            )
        return ParseResult(pages=pages)

    @staticmethod
    def _ground(
        raw: list[RawElement], page_no: int
    ) -> tuple[list[GroundedElement], int]:
        """The ground-check (§9 rule 1): no box, no text, or no confidence
        means the element is thrown away — not down-scored, not repaired."""
        grounded: list[GroundedElement] = []
        discarded = 0
        for element in raw:
            if (
                element.bbox is None
                or not element.bbox.is_valid()
                or not element.text
                or not element.text.strip()
                or element.confidence is None
                or not 0.0 <= element.confidence <= 1.0
            ):
                discarded += 1
                continue
            grounded.append(
                GroundedElement(
                    kind=element.kind,
                    text=element.text,
                    bbox=element.bbox,
                    confidence=element.confidence,
                    page_no=page_no,
                    seq=len(grounded),
                )
            )
        return grounded, discarded
