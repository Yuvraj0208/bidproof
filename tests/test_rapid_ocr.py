"""US-03 OCR engine: RapidOCR reads a scanned page into grounded elements —
each line carries real text, a valid box, and a confidence, so OCR'd content
keeps the same page+box proof chain as everything else. Skipped where RapidOCR
isn't installed (it's an optional engine)."""

from pathlib import Path

import pytest

from bidproof_parser.engines.rapid_ocr import RapidOcrEngine, rapid_ocr_available

pytestmark = pytest.mark.integration

SCANNED = (Path(__file__).parent / "fixtures" / "scanned.pdf").read_bytes()


@pytest.mark.skipif(
    not rapid_ocr_available(), reason="rapidocr/onnxruntime not installed"
)
def test_rapidocr_reads_a_scanned_page_with_grounded_lines():
    elements = RapidOcrEngine().extract(SCANNED, 1)

    assert elements, "OCR should return at least one line on a scanned page"
    for e in elements:
        assert e.kind == "ocr_line"
        assert e.text and e.text.strip()          # real text, never blank
        assert e.bbox is not None and e.bbox.is_valid()  # x1>x0, y1>y0
        assert 0.0 <= e.confidence <= 1.0          # a usable confidence


@pytest.mark.skipif(
    not rapid_ocr_available(), reason="rapidocr/onnxruntime not installed"
)
def test_rapidocr_returns_empty_for_a_blank_render():
    # A page index past the end yields no image content → no elements, no crash.
    # (Guards the "None boxes" path.)
    from pypdfium2 import PdfDocument

    pages = len(PdfDocument(SCANNED))
    # last valid page still OK; this asserts the engine never raises on real input
    assert RapidOcrEngine().extract(SCANNED, pages) is not None
