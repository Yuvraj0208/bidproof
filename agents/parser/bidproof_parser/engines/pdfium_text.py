"""Built-in step-1 extractor: reads the born-digital text layer with
pypdfium2, using pdfium's own text-rect segmentation (one rect per line
run) for the bounding boxes.

This is the zero-dependency fallback so the pipeline works end to end
without the ML extras. Docling (layout, reading order, rebuilt tables)
replaces it wherever the `ml` extra is installed.
"""

import pypdfium2 as pdfium

from bidproof_parser.types import BBox, RawElement

# The text layer of a born-digital PDF is exact, but segmentation is
# heuristic — kept just below 1.0 so calibration stays honest (§9 rule 8).
BORN_DIGITAL_CONFIDENCE = 0.95


class PdfiumTextExtractor:
    def extract(
        self, pdf_bytes: bytes, page_numbers: list[int]
    ) -> dict[int, list[RawElement]]:
        pdf = pdfium.PdfDocument(pdf_bytes)
        try:
            return {n: self._extract_page(pdf, n) for n in page_numbers}
        finally:
            pdf.close()

    def _extract_page(self, pdf: pdfium.PdfDocument, page_no: int) -> list[RawElement]:
        page = pdf[page_no - 1]
        _, height = page.get_size()
        textpage = page.get_textpage()
        try:
            elements = []
            for index in range(textpage.count_rects()):
                left, bottom, right, top = textpage.get_rect(index)
                text = textpage.get_text_bounded(
                    left=left, bottom=bottom, right=right, top=top
                ).strip()
                if not text:
                    continue
                elements.append(
                    RawElement(
                        kind="text_line",
                        text=text,
                        # pdfium boxes are bottom-left origin; normalise to
                        # top-left to match the parser's coordinate contract.
                        bbox=BBox(
                            x0=left, y0=height - top, x1=right, y1=height - bottom
                        ),
                        confidence=BORN_DIGITAL_CONFIDENCE,
                    )
                )
            return elements
        finally:
            textpage.close()
            page.close()
