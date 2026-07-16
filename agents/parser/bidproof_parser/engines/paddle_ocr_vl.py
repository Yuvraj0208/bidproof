"""Step-2 production OCR: PaddleOCR-VL on a 300 dpi render of the page.

Heavy install (paddlepaddle + paddleocr, per their platform instructions) —
lazy import. When absent, the wiring falls back to UnavailableOcrEngine and
scan pages are flagged to a human instead of guessed at.
"""

import pypdfium2 as pdfium

from bidproof_parser.types import BBox, RawElement

_RENDER_DPI = 300
_SCALE = _RENDER_DPI / 72  # PDF points are 1/72 inch


def paddle_ocr_available() -> bool:
    try:
        import paddleocr  # noqa: F401

        return True
    except ImportError:
        return False


class PaddleOcrVlEngine:
    def __init__(self) -> None:
        from paddleocr import PaddleOCR

        self._ocr = PaddleOCR(use_angle_cls=True)

    def extract(self, pdf_bytes: bytes, page_no: int) -> list[RawElement]:
        import numpy as np

        pdf = pdfium.PdfDocument(pdf_bytes)
        try:
            page = pdf[page_no - 1]
            bitmap = page.render(scale=_SCALE)
            image = np.asarray(bitmap.to_pil().convert("RGB"))
            page.close()
        finally:
            pdf.close()

        elements: list[RawElement] = []
        for result in self._ocr.ocr(image) or []:
            for line in result or []:
                box, (text, score) = line[0], line[1]
                if not text or not text.strip():
                    continue
                xs = [point[0] / _SCALE for point in box]
                ys = [point[1] / _SCALE for point in box]
                elements.append(
                    RawElement(
                        kind="ocr_line",
                        text=text,
                        bbox=BBox(x0=min(xs), y0=min(ys), x1=max(xs), y1=max(ys)),
                        confidence=float(score),
                    )
                )
        return elements
