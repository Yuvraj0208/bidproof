"""Step-2 OCR via RapidOCR on a 300 dpi render of the page.

RapidOCR runs the same PP-OCR detection/recognition models as PaddleOCR-VL but
through onnxruntime instead of paddlepaddle — which makes it portable to CPUs
and OSes where paddlepaddle's inference backend does not run (e.g. some Windows
CPU builds). Lazy import; when absent the wiring falls back to
UnavailableOcrEngine and scan pages are flagged to a human, never guessed.

Every returned line carries its own box + confidence, so OCR'd text keeps the
same page+box grounding as everything else in the pipeline.
"""

import pypdfium2 as pdfium

from bidproof_parser.types import BBox, RawElement

_RENDER_DPI = 300
_SCALE = _RENDER_DPI / 72  # PDF points are 1/72 inch


def rapid_ocr_available() -> bool:
    try:
        import onnxruntime  # noqa: F401
        import rapidocr  # noqa: F401

        return True
    except ImportError:
        return False


class RapidOcrEngine:
    def __init__(self) -> None:
        from rapidocr import RapidOCR

        self._ocr = RapidOCR()

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

        result = self._ocr(image)
        if result is None or result.boxes is None:
            return []

        elements: list[RawElement] = []
        for box, text, score in zip(result.boxes, result.txts, result.scores):
            if not text or not text.strip():
                continue
            # box is a 4-point polygon in rendered-image pixels; back to points.
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
