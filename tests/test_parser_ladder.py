"""US-03: the 4-step reader ladder. Routing, ground-check, flagging.

Uses the real pypdfium2 step 0 and built-in text extractor against fixture
PDFs; OCR engines are fakes (the heavy ML engines have their own guarded
tests and the gold-set harness later — routing logic is what US-03 owns).
"""

import io
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


def _pdf_with_mangled_text_layer() -> bytes:
    """A page with plenty of characters that decode to nothing readable.

    This is the real case OCR exists for: broken encodings and exotic CID fonts,
    where the file HAS a text layer (so step 0 routes it to TEXT) but no reader
    can make words out of it. Written as a genuine fixture rather than a faked
    extractor result, so the page is unreadable all the way down — pdfium reads
    it back as U+25A0 and friends, exactly as it reads a real mangled tender.
    """
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    junk = "■□▒░▓●○" * 8
    for _ in range(2):
        pdf.setFont("Helvetica", 12)
        pdf.drawString(72, 760, junk)
        pdf.drawString(72, 740, junk)
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


MANGLED = _pdf_with_mangled_text_layer()


def test_ladder_reroutes_garbage_text_page_to_ocr():
    garbage = [
        RawElement("text_line", "������", BBox(1, 1, 5, 5), 0.9)
    ]
    ocr = FakeOcr(confidence=0.9)
    ladder = ParserLadder(FakeText({1: garbage, 2: garbage}), ocr)
    result = ladder.parse(MANGLED)

    assert sorted(ocr.calls) == [1, 2]
    assert all(p.route is PageRoute.OCR for p in result.pages)
    # Nothing was recoverable, so the cheap retry must not have claimed a win.
    assert ladder.pages_recovered_by_pdfium == 0


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


# --- A PDF with a picture in it (the case that broke a real tender) ---------
#
# Every fixture above is reportlab text-only, which is exactly why the suite was
# green while a real government PDF failed: docling's PictureItem has no `.text`
# and its export_to_markdown() REQUIRES the document, so calling it bare raised
# TypeError and — uncaught — failed the parse of the whole document. One logo
# destroyed an 800-page tender.


def _pdf_with_picture() -> bytes:
    """Two text lines and an embedded image on the same page."""
    import io

    from reportlab.lib.pagesizes import letter
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    # A tiny solid-colour PNG standing in for a letterhead logo.
    png = io.BytesIO()
    try:
        from PIL import Image

        Image.new("RGB", (48, 48), (20, 33, 112)).save(png, format="PNG")
    except ImportError:  # pragma: no cover - PIL ships with reportlab's deps
        return b""
    png.seek(0)

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.drawImage(ImageReader(png), 72, 700, width=48, height=48)
    pdf.setFont("Helvetica", 11)
    pdf.drawString(72, 660, "TENDER NOTICE No. 42/2026")
    pdf.drawString(72, 640, "Earnest Money Deposit: Rs 2,50,000 payable at submission.")
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def test_a_pdf_containing_a_picture_still_parses():
    """The picture must cost at most itself — never the document."""
    pdf_bytes = _pdf_with_picture()
    if not pdf_bytes:
        import pytest

        pytest.skip("reportlab/PIL not available to build the fixture")

    ladder = ParserLadder(PdfiumTextExtractor(), UnavailableOcrEngine())
    result = ladder.parse(pdf_bytes)

    assert result.pages_total == 1
    text = " ".join(e.text for p in result.pages for e in p.elements)
    assert "Earnest Money Deposit" in text


class ExplodingExtractor:
    """Stands in for a text engine whose library breaks on real input."""

    def extract(self, pdf_bytes, page_numbers):
        raise TypeError("export_to_markdown() missing 1 required positional argument")


def test_a_failing_text_engine_falls_back_instead_of_losing_the_document():
    ladder = ParserLadder(ExplodingExtractor(), UnavailableOcrEngine())
    result = ladder.parse(DIGITAL)

    # The run survives, the pages are still read, and the ladder admits it fell back.
    assert result.pages_total == 2
    assert ladder.text_extractor_fell_back is True
    text = " ".join(e.text for p in result.pages for e in p.elements)
    assert "Earnest Money Deposit" in text


# --- The exact failure, pinned at the unit level ---------------------------


def test_item_text_handles_a_picture_that_needs_the_document():
    """Reproduces the real crash: an item with no `.text` whose exporter demands
    the document. Bare-calling it raised TypeError and failed the whole parse."""
    from bidproof_parser.engines.docling_engine import item_text

    class PictureLike:
        """No `.text`; export_to_markdown REQUIRES doc (docling 2.114 behaviour)."""

        def export_to_markdown(self, doc=None, **_):
            if doc is None:
                raise TypeError(
                    "export_to_markdown() missing 1 required positional argument: 'doc'"
                )
            return "<!-- image -->"

    # Must not raise, and an uncaptioned image is NOT text — it is skipped.
    assert item_text(PictureLike(), document=object()) == ""


def test_item_text_prefers_real_text_and_keeps_a_caption():
    from bidproof_parser.engines.docling_engine import item_text

    class TextLike:
        text = "Earnest Money Deposit: Rs 2,50,000"

    class CaptionedPicture:
        def export_to_markdown(self, doc=None, **_):
            return "Figure 1: site layout"

    assert item_text(TextLike(), None) == "Earnest Money Deposit: Rs 2,50,000"
    assert item_text(CaptionedPicture(), object()) == "Figure 1: site layout"


def test_item_text_never_raises_on_a_hostile_item():
    from bidproof_parser.engines.docling_engine import item_text

    class Broken:
        def export_to_markdown(self, doc=None, **_):
            raise RuntimeError("corrupt item")

    assert item_text(Broken(), object()) == ""


# --- Step 1b: don't pay for OCR when the text layer is right there ----------


class AmnesiacExtractor:
    """A text engine that silently loses pages instead of raising.

    This is the real Docling failure mode observed on a 283-page tender: the
    preprocess stage died with `std::bad_alloc`, the exception never reached us,
    and the converter simply returned a document with those pages missing.
    """

    def __init__(self, lose: set[int]):
        self.lose = lose

    def extract(self, pdf_bytes, page_numbers):
        from bidproof_parser.engines.pdfium_text import PdfiumTextExtractor

        real = PdfiumTextExtractor().extract(pdf_bytes, page_numbers)
        return {n: ([] if n in self.lose else els) for n, els in real.items()}


def test_a_page_the_engine_lost_is_recovered_from_the_text_layer_not_ocr():
    ocr = FakeOcr()
    ladder = ParserLadder(AmnesiacExtractor(lose={1}), ocr)
    result = ladder.parse(DIGITAL)

    # Page 1 has a real text layer, so it must never reach the OCR engine —
    # OCR costs ~45 s a page to re-read text the file already contains.
    assert ocr.calls == []
    page_one = result.pages[0]
    assert page_one.route is PageRoute.TEXT
    assert page_one.elements, "page 1 should have been recovered by pdfium"
    assert ladder.pages_recovered_by_pdfium == 1


def test_a_genuinely_unreadable_text_layer_still_goes_to_ocr():
    """The cheap retry must not swallow the case OCR exists for."""
    ocr = FakeOcr()
    # No text layer at all: pdfium has nothing to recover, so OCR must run.
    ladder = ParserLadder(AmnesiacExtractor(lose=set()), ocr)
    result = ladder.parse(SCANNED)

    assert sorted(ocr.calls) == [1, 2]
    assert ladder.pages_recovered_by_pdfium == 0
    assert all(p.route is PageRoute.OCR for p in result.pages)


def test_the_retry_is_skipped_when_pdfium_is_already_the_engine():
    """Retrying the same reader that just failed would prove nothing."""
    from bidproof_parser.engines.pdfium_text import PdfiumTextExtractor

    ocr = FakeOcr()
    ladder = ParserLadder(PdfiumTextExtractor(), ocr)
    ladder.parse(DIGITAL)
    assert ladder.pages_recovered_by_pdfium == 0


def test_item_text_drops_docling_placeholder_comments():
    """Docling narrating its own limits is not tender content.

    On a live GeM tender the first two elements of page 1 were
    `<!-- 🖼️❌ Image not available. Please use PdfPipelineOptions(...) -->`.
    Those would have been indexed, retrieved and quoted as if the tender said
    them.
    """
    from bidproof_parser.engines.docling_engine import item_text

    class Rendered:
        def __init__(self, markdown):
            self._markdown = markdown

        def export_to_markdown(self, doc=None):
            return self._markdown

    assert item_text(Rendered("<!-- image -->"), None) == ""
    assert (
        item_text(
            Rendered(
                "<!-- \U0001f5bc️❌ Image not available. Please use "
                "`PdfPipelineOptions(generate_picture_images=True)` -->"
            ),
            None,
        )
        == ""
    )
    assert item_text(Rendered("<!-- image --><!-- image -->"), None) == ""
    # Real content that merely CONTAINS a comment is still content.
    assert item_text(Rendered("<!-- image -->\nClause 4.2: EMD is Rs 5,00,000"), None)
    assert item_text(Rendered("Turnover must exceed Rs 50 crore"), None)
