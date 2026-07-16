"""US-03: the 4-step reader ladder. Routing, ground-check, flagging.

Uses the real pypdfium2 step 0 and built-in text extractor against fixture
PDFs; OCR engines are fakes (the heavy ML engines have their own guarded
tests and the gold-set harness later — routing logic is what US-03 owns).
"""

from pathlib import Path

from bidproof_parser import (
    BBox,
    PageRoute,
    PageStatus,
    ParserLadder,
    RawElement,
    compute_parse_cost_inr,
    inspect_pages,
)
from bidproof_parser.engines import PdfiumTextExtractor, UnavailableOcrEngine

FIXTURES = Path(__file__).parent / "fixtures"

DIGITAL = (FIXTURES / "digital.pdf").read_bytes()
SCANNED = (FIXTURES / "scanned.pdf").read_bytes()
MIXED = (FIXTURES / "mixed.pdf").read_bytes()


class FakeOcr:
    def __init__(self, confidence: float = 0.9):
        self.confidence = confidence
        self.calls: list[int] = []

    def extract(self, pdf_bytes: bytes, page_no: int) -> list[RawElement]:
        self.calls.append(page_no)
        return [
            RawElement(
                kind="ocr_line",
                text=f"ocr text from page {page_no}",
                bbox=BBox(72, 90, 400, 110),
                confidence=self.confidence,
            )
        ]


class FakeText:
    def __init__(self, per_page: dict[int, list[RawElement]]):
        self.per_page = per_page

    def extract(self, pdf_bytes, page_numbers):
        return {n: self.per_page.get(n, []) for n in page_numbers}


# --- Step 0: routing -------------------------------------------------------


def test_step0_routes_digital_pages_as_text():
    infos = inspect_pages(DIGITAL)
    assert len(infos) == 2
    assert all(info.char_count >= 25 for info in infos)
    assert all(info.width > 0 and info.height > 0 for info in infos)


def test_step0_routes_scanned_pages_as_ocr():
    infos = inspect_pages(SCANNED)
    assert len(infos) == 2
    assert all(info.char_count < 25 for info in infos)


def test_step0_mixed_pdf_splits_routes():
    infos = inspect_pages(MIXED)
    assert infos[0].char_count >= 25
    assert infos[1].char_count < 25


# --- The ladder ------------------------------------------------------------


def test_ladder_sends_scanned_pages_to_ocr_engine():
    ocr = FakeOcr(confidence=0.9)
    ladder = ParserLadder(PdfiumTextExtractor(), ocr)
    result = ladder.parse(SCANNED)

    assert ocr.calls == [1, 2]
    assert all(p.route is PageRoute.OCR for p in result.pages)
    assert all(p.status is PageStatus.PARSED for p in result.pages)
    assert not result.needs_human


def test_ladder_flags_low_confidence_page_for_human():
    ladder = ParserLadder(PdfiumTextExtractor(), FakeOcr(confidence=0.3))
    result = ladder.parse(SCANNED)

    assert all(p.status is PageStatus.FLAGGED for p in result.pages)
    assert result.needs_human
    # Elements are kept for the human to review — flagged, not deleted.
    assert all(p.elements for p in result.pages)


def test_ladder_discards_ungrounded_elements():
    good = RawElement("text_line", "grounded", BBox(10, 10, 100, 30), 0.9)
    no_box = RawElement("text_line", "no box", None, 0.9)
    empty_text = RawElement("text_line", "   ", BBox(10, 10, 100, 30), 0.9)
    no_conf = RawElement("text_line", "no confidence", BBox(10, 10, 100, 30), None)
    inverted_box = RawElement("text_line", "bad box", BBox(100, 30, 10, 10), 0.9)

    fake = FakeText({1: [good, no_box, empty_text, no_conf, inverted_box],
                     2: [good]})
    ladder = ParserLadder(fake, FakeOcr())
    result = ladder.parse(DIGITAL)

    page1 = result.pages[0]
    assert [e.text for e in page1.elements] == ["grounded"]
    assert page1.discarded == 4
    assert result.elements_discarded == 4


def test_ladder_reroutes_garbage_text_page_to_ocr():
    garbage = [
        RawElement("text_line", "������", BBox(1, 1, 5, 5), 0.9)
    ]
    ocr = FakeOcr(confidence=0.9)
    ladder = ParserLadder(FakeText({1: garbage, 2: garbage}), ocr)
    result = ladder.parse(DIGITAL)

    assert sorted(ocr.calls) == [1, 2]
    assert all(p.route is PageRoute.OCR for p in result.pages)


def test_ladder_flags_page_with_no_elements_at_all():
    ladder = ParserLadder(PdfiumTextExtractor(), UnavailableOcrEngine())
    result = ladder.parse(SCANNED)

    assert all(p.status is PageStatus.FLAGGED for p in result.pages)
    assert all(p.confidence == 0.0 for p in result.pages)
    assert result.needs_human


# --- Born-digital end to end (AC: a born-digital PDF) ----------------------


def test_pdfium_extractor_grounds_born_digital_elements():
    elements = PdfiumTextExtractor().extract(DIGITAL, [1, 2])
    texts = [e.text for e in elements[1]]

    assert any("TENDER NOTICE" in t for t in texts)
    assert all(e.bbox is not None and e.bbox.is_valid() for e in elements[1])
    assert all(e.confidence and 0 < e.confidence < 1 for e in elements[1])


def test_ladder_parses_born_digital_pdf_without_ml_engines():
    ladder = ParserLadder(PdfiumTextExtractor(), UnavailableOcrEngine())
    result = ladder.parse(DIGITAL)

    assert result.pages_total == 2
    assert all(p.route is PageRoute.TEXT for p in result.pages)
    assert all(p.status is PageStatus.PARSED for p in result.pages)
    assert not result.needs_human
    for page in result.pages:
        for element in page.elements:
            assert element.text.strip()
            assert element.bbox.is_valid()
            assert 0 <= element.confidence <= 1
            assert element.page_no == page.page_no


def test_mixed_pdf_without_ocr_flags_only_the_scan_page():
    ladder = ParserLadder(PdfiumTextExtractor(), UnavailableOcrEngine())
    result = ladder.parse(MIXED)

    assert result.pages[0].route is PageRoute.TEXT
    assert result.pages[0].status is PageStatus.PARSED
    assert result.pages[1].route is PageRoute.OCR
    assert result.pages[1].status is PageStatus.FLAGGED
    assert result.needs_human


# --- Cost (AC: logged with cost; §9 rule 2: never model arithmetic) --------


def test_parse_cost_is_deterministic():
    assert compute_parse_cost_inr(3, 1.25) == 3.75
    assert compute_parse_cost_inr(0, 1.25) == 0.0
    assert compute_parse_cost_inr(5, 0.0) == 0.0
