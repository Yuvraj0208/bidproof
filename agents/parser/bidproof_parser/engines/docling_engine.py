"""Step-1 production extractor: Docling (layout, reading order, tables).

Heavy install — lives behind the `ml` extra and a lazy import. Selected
automatically by the wiring when importable; otherwise the built-in
pdfium extractor covers born-digital pages.
"""

import io

from bidproof_parser.types import BBox, RawElement

# Docling reports rich layout but no per-item score for born-digital text;
# held just below 1.0 until the gold set calibrates it (§9 rule 8).
DOCLING_CONFIDENCE = 0.97


def docling_available() -> bool:
    try:
        import docling  # noqa: F401

        return True
    except ImportError:
        return False


class DoclingTextExtractor:
    def __init__(self) -> None:
        from docling.document_converter import DocumentConverter

        self._converter = DocumentConverter()

    def extract(
        self, pdf_bytes: bytes, page_numbers: list[int]
    ) -> dict[int, list[RawElement]]:
        from docling.datamodel.base_models import DocumentStream

        wanted = set(page_numbers)
        result = self._converter.convert(
            DocumentStream(name="document.pdf", stream=io.BytesIO(pdf_bytes))
        )
        pages: dict[int, list[RawElement]] = {n: [] for n in page_numbers}

        for item, _level in result.document.iterate_items():
            for prov in getattr(item, "prov", []) or []:
                page_no = prov.page_no
                if page_no not in wanted:
                    continue
                text = getattr(item, "text", None) or getattr(
                    item, "export_to_markdown", lambda: ""
                )()
                if not text or not text.strip():
                    continue
                page = result.document.pages[page_no]
                height = page.size.height
                bb = prov.bbox
                # Docling boxes are bottom-left origin; normalise to top-left.
                pages[page_no].append(
                    RawElement(
                        kind=str(getattr(item, "label", "text")),
                        text=text,
                        bbox=BBox(
                            x0=bb.l, y0=height - bb.t, x1=bb.r, y1=height - bb.b
                        ),
                        confidence=DOCLING_CONFIDENCE,
                    )
                )
        return pages
