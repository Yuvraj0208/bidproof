"""The 4-step reader ladder (SPEC §5.2), cheapest step first.

Step 0  pypdfium2: does the page have a real text layer, or is it a picture?
Step 1  real text  -> TextExtractor (Docling in production).
Step 2  scan/wrong -> OcrEngine (PaddleOCR-VL in production, 300 dpi).
Step 3  still wrong -> the page is FLAGGED for a human. Never guess.

The ground-check runs on every engine output: an element without real text,
a valid box, and a confidence is discarded and counted — it does not exist.
"""

import logging
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


logger = logging.getLogger(__name__)


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
        # Set when step 1 had to drop to the built-in reader.
        self.text_extractor_fell_back = False
        # Pages the configured extractor lost but pdfium read anyway.
        self.pages_recovered_by_pdfium = 0

    def _extract_text(
        self, pdf_bytes: bytes, text_pages: list[int]
    ) -> dict[int, list[RawElement]]:
        """Step 1, with the ladder's own rule applied to itself.

        The ladder degrades honestly when an engine is MISSING; it must do the
        same when an engine FAILS. A crash in the configured extractor used to
        propagate all the way out and fail the whole parse run, so one
        unreadable item in a real tender lost the entire document. Falling back
        to the built-in pdfium reader keeps the pages, and the caller still gets
        every element it can be given.
        """
        try:
            return self._text_extractor.extract(pdf_bytes, text_pages)
        except Exception as exc:
            logger.warning(
                "text extractor %s failed (%s); falling back to pdfium",
                type(self._text_extractor).__name__, exc,
            )
            self.text_extractor_fell_back = True
            try:
                from bidproof_parser.engines.pdfium_text import PdfiumTextExtractor

                return PdfiumTextExtractor().extract(pdf_bytes, text_pages)
            except Exception as fallback_exc:
                # Both readers are gone. Return nothing rather than raise: the
                # pages will route to OCR or be flagged for a human, which is
                # the ladder's last honest step.
                logger.error("pdfium fallback also failed: %s", fallback_exc)
                return {}

    def _retry_with_pdfium(
        self, pdf_bytes: bytes, pages: list[int]
    ) -> dict[int, list[RawElement]]:
        """Re-read `pages` with the built-in reader, keeping only real gains.

        A page is only replaced when pdfium returns something that does NOT look
        like garbage — a genuinely mangled text layer (broken CID fonts) still
        reads as garbage here and correctly falls through to OCR.
        """
        from bidproof_parser.engines.pdfium_text import PdfiumTextExtractor

        if isinstance(self._text_extractor, PdfiumTextExtractor):
            return {}  # already the fallback; retrying it would prove nothing

        try:
            recovered = PdfiumTextExtractor().extract(pdf_bytes, pages)
        except Exception as exc:
            logger.warning("pdfium retry failed for %d page(s): %s", len(pages), exc)
            return {}

        gained = {
            page_no: elements
            for page_no, elements in recovered.items()
            if not looks_like_garbage(elements)
        }
        if gained:
            self.pages_recovered_by_pdfium += len(gained)
            logger.warning(
                "%s returned nothing usable for %d page(s); pdfium recovered %d "
                "of them from the existing text layer",
                type(self._text_extractor).__name__, len(pages), len(gained),
            )
        return gained

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
            self._extract_text(pdf_bytes, text_pages) if text_pages else {}
        )

        # Step 1b: the page HAS a text layer (step 0 counted the characters),
        # so before paying for OCR, try the cheap built-in reader on whatever
        # the configured extractor did not manage to return.
        #
        # This is not hypothetical. On a real 283-page tender, Docling hit
        # `std::bad_alloc` while preprocessing and silently returned nothing for
        # those pages — it did not raise, so the fallback in `_extract_text`
        # never fired. Those pages then went to OCR at ~45 s each to re-read
        # text that was already sitting in the file. Cheapest step first is the
        # ladder's whole point (SPEC §5.2).
        retry = [n for n in text_pages if looks_like_garbage(extracted.get(n, []))]
        if retry:
            extracted.update(self._retry_with_pdfium(pdf_bytes, retry))

        # Step 2 rerouting: a "text" page whose extraction still looks wrong
        # gets one honest retry through OCR before anyone gives up on it.
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
