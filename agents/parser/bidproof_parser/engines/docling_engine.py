"""Step-1 production extractor: Docling (layout, reading order, tables).

Heavy install — lives behind the `ml` extra and a lazy import. Selected
automatically by the wiring when importable; otherwise the built-in
pdfium extractor covers born-digital pages.
"""

import io
import logging
import re

from bidproof_parser.types import BBox, RawElement

logger = logging.getLogger(__name__)

# Docling reports rich layout but no per-item score for born-digital text;
# held just below 1.0 until the gold set calibrates it (§9 rule 8).
DOCLING_CONFIDENCE = 0.97

# A render consisting only of HTML comments carries no tender content.
_COMMENT_ONLY_RE = re.compile(r"(?:\s*<!--.*?-->\s*)+", re.DOTALL)


def docling_available() -> bool:
    try:
        import docling  # noqa: F401

        return True
    except ImportError:
        return False


def item_text(item, document) -> str:
    """The text of one Docling item, or "" if it has none.

    Not every item is text. A PictureItem has no `.text` at all, and its
    `export_to_markdown(doc, ...)` REQUIRES the document — calling it bare raised
    `TypeError: missing 1 required positional argument` and, because nothing
    caught it, failed the parse of the entire tender. One logo destroyed an
    800-page document (docling 2.114.0).

    A picture with no caption is not text, and must never be invented into an
    element — returning "" lets the caller skip it, which is the honest outcome.
    """
    text = getattr(item, "text", None)
    if isinstance(text, str) and text.strip():
        return text

    exporter = getattr(item, "export_to_markdown", None)
    if exporter is None:
        return ""
    try:
        # Items that render themselves (tables, captioned pictures) need the
        # document for context; older items accept no argument at all.
        try:
            rendered = exporter(doc=document)
        except TypeError:
            rendered = exporter()
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("docling item %r could not render: %s", type(item).__name__, exc)
        return ""

    if not isinstance(rendered, str):
        return ""
    stripped = rendered.strip()
    # Docling renders an image it cannot express as an HTML comment — either
    # `<!-- image -->` or a longer "Image not available, use PdfPipelineOptions"
    # note. Both are the TOOL talking about itself, not tender content, and both
    # were leaking into elements as real text (seen on a live GeM tender: 8435
    # elements, the first two of them placeholders). A render that is nothing but
    # a comment is not text.
    if _COMMENT_ONLY_RE.fullmatch(stripped):
        return ""
    return rendered


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

        skipped = 0
        for item, _level in result.document.iterate_items():
            for prov in getattr(item, "prov", []) or []:
                # A single malformed item costs one element, never the document.
                try:
                    page_no = prov.page_no
                    if page_no not in wanted:
                        continue
                    text = item_text(item, result.document)
                    if not text.strip():
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
                except Exception as exc:
                    skipped += 1
                    logger.warning(
                        "docling: skipped a %s item: %s", type(item).__name__, exc
                    )
        if skipped:
            logger.warning("docling skipped %d unreadable item(s)", skipped)
        return pages
