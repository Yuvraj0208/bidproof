"""Evaluating the reader ladder: OCR accuracy, and whether Docling earns its keep.

Both evaluators here measure the real engines the API uses — the same
`get_ladder()` wiring, not a copy — so a number here is a number about
production.

**OCR ground truth is generated, and that is the honest way to get it.** We
render known sentences to a page, flatten that page to an image so no text layer
survives, and hand it back to the OCR engine. The answer is known exactly because
we wrote it, which makes character error rate a true measurement rather than an
estimate. Its limit is equally clear and is reported alongside: it tests clean
rendered text, not a smudged 1998 photocopy, so it is an upper bound on quality.

**Docling versus pypdfium2 needs no labels at all.** Running both over the same
PDFs and comparing what each recovered answers the question that actually
matters — is the heavy engine returning more than the cheap one, and how often
does it lose a page? On this project that is not hypothetical: Docling hit
`std::bad_alloc` on a real tender and silently returned nothing for those pages.
"""

from __future__ import annotations

import io
import time

from app.services.evaluation.types import Evaluation, GroundTruth, Metric, Status

# Sentences with the shapes a tender actually contains: rupee amounts, clause
# numbers, dates, standards. Reading "hello world" back correctly would prove
# very little about reading an EMD figure.
OCR_GROUND_TRUTH = [
    "Earnest Money Deposit of Rs 2,50,000 shall be furnished",
    "Minimum average annual turnover of Rs 5 crore in last 3 years",
    "Delivery shall be completed within 90 days from the date of order",
    "Performance Bank Guarantee at 5 percent of the contract value",
    "The bidder shall hold a valid ISO 9001:2015 certificate",
    "Bids close on 24-08-2026 at 15:00 hours",
]


def _levenshtein(a: str, b: str) -> int:
    """Edit distance. Written out rather than pulled in as a dependency: it is
    twelve lines and this is the only place the project needs it."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(
                min(
                    previous[j] + 1,        # deletion
                    current[j - 1] + 1,     # insertion
                    previous[j - 1] + (ca != cb),  # substitution
                )
            )
        previous = current
    return previous[-1]


def _normalise(text: str) -> str:
    """Compare on content, not on whitespace or case.

    OCR line-breaks and capitalisation are not accuracy problems for this
    product — the extractor normalises both before it looks for a number.
    """
    return " ".join(text.lower().split())


def _scanned_pdf(lines: list[str]) -> bytes:
    """A PDF whose pages are IMAGES of the given text, with no text layer.

    Drawing text and then rasterising it is the point: it guarantees the reader
    ladder must route the page to OCR, which is what we are trying to measure.
    """
    import pypdfium2 as pdfium
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setFont("Helvetica", 13)
    y = 760
    for line in lines:
        pdf.drawString(60, y, line)
        y -= 34
    pdf.showPage()
    pdf.save()

    # Flatten to an image so no text layer remains.
    source = pdfium.PdfDocument(buffer.getvalue())
    bitmap = source[0].render(scale=200 / 72)
    image = bitmap.to_pil()
    source.close()

    out = io.BytesIO()
    image.save(out, format="PDF", resolution=200.0)
    return out.getvalue()


def evaluate_ocr() -> Evaluation:
    started = time.monotonic()
    base = Evaluation(
        component="ocr",
        label="OCR (RapidOCR)",
        what_it_measures=(
            "Character error rate reading text off a page image, against text "
            "we rendered ourselves so the correct answer is known exactly."
        ),
        status=Status.ERROR,
        ground_truth=GroundTruth.SYNTHETIC,
    )

    from app.parsing import get_ladder

    ladder = get_ladder()
    engine = ladder._ocr_engine
    engine_name = type(engine).__name__
    if engine_name == "UnavailableOcrEngine":
        base.status = Status.NO_GROUND_TRUTH
        base.blocked_reason = "No OCR engine is installed, so scans are flagged to a human."
        base.how_to_fix = "Install the ml extra so RapidOCR is importable."
        return base

    try:
        pdf_bytes = _scanned_pdf(OCR_GROUND_TRUTH)
        elements = engine.extract(pdf_bytes, 1)
    except Exception as exc:  # pragma: no cover - environment dependent
        base.blocked_reason = f"{type(exc).__name__}: {exc}"[:300]
        base.how_to_fix = "Check the OCR engine install (onnxruntime models download on first use)."
        return base

    read = _normalise(" ".join(e.text for e in elements))
    truth = _normalise(" ".join(OCR_GROUND_TRUTH))

    distance = _levenshtein(truth, read)
    cer = distance / max(len(truth), 1)

    truth_words = truth.split()
    read_words = set(read.split())
    words_found = sum(1 for w in truth_words if w in read_words)

    # The figures are what a bid is won or lost on, so score them separately.
    figures = ["2,50,000", "5", "90", "9001:2015", "24-08-2026", "15:00"]
    figures_found = sum(1 for f in figures if _normalise(f) in read)

    base.status = Status.MEASURED
    base.duration_s = round(time.monotonic() - started, 2)
    base.metrics = [
        Metric(
            key="cer",
            label="Character error rate",
            value=round(cer, 4),
            unit="ratio",
            higher_is_better=False,
            sample_size=len(truth),
            detail=f"{distance} edits over {len(truth)} characters, engine {engine_name}",
        ),
        Metric(
            key="word_recall",
            label="Words read correctly",
            value=round(words_found / max(len(truth_words), 1), 4),
            unit="ratio",
            sample_size=len(truth_words),
        ),
        Metric(
            key="figure_recall",
            label="Figures read exactly",
            value=round(figures_found / len(figures), 4),
            unit="ratio",
            sample_size=len(figures),
            detail="amounts, percentages, dates and standard numbers",
        ),
        Metric(
            key="elements",
            label="Elements returned",
            value=float(len(elements)),
            unit="count",
            sample_size=len(OCR_GROUND_TRUTH),
        ),
    ]
    return base


def evaluate_text_engines(sample: int = 6) -> Evaluation:
    """Docling against the built-in pypdfium2 reader, over the gold PDFs.

    No labels needed: the question is whether the expensive engine returns more
    than the cheap one, and how often it returns nothing for a page it was given.
    """
    from pathlib import Path

    started = time.monotonic()
    base = Evaluation(
        component="text_engines",
        label="Text extraction (Docling vs pypdfium2)",
        what_it_measures=(
            "Whether the heavy layout engine recovers more than the built-in "
            "reader on the same pages, and how often it loses a page entirely."
        ),
        status=Status.ERROR,
        ground_truth=GroundTruth.DERIVED,
    )

    gold = Path(__file__).resolve().parents[5] / "tests" / "gold"
    pdfs = sorted(gold.glob("gold-*/tender.pdf"))[:sample]
    if not pdfs:
        base.status = Status.NO_GROUND_TRUTH
        base.blocked_reason = "No PDFs found under tests/gold to compare on."
        base.how_to_fix = "Add tender PDFs to tests/gold/<case>/tender.pdf."
        return base

    from bidproof_parser.engines.pdfium_text import PdfiumTextExtractor
    from bidproof_parser.engines.docling_engine import docling_available
    from bidproof_parser.ladder import inspect_pages

    if not docling_available():
        base.status = Status.NO_GROUND_TRUTH
        base.blocked_reason = "Docling is not installed, so there is nothing to compare."
        base.how_to_fix = "Install the ml extra."
        return base

    from bidproof_parser.engines.docling_engine import DoclingTextExtractor

    docling = DoclingTextExtractor()
    pdfium = PdfiumTextExtractor()

    d_chars = p_chars = 0
    d_time = p_time = 0.0
    pages_total = pages_docling_empty = 0

    for path in pdfs:
        data = path.read_bytes()
        text_pages = [i.page_no for i in inspect_pages(data) if i.char_count >= 25]
        if not text_pages:
            continue
        pages_total += len(text_pages)

        t0 = time.monotonic()
        d_out = docling.extract(data, text_pages)
        d_time += time.monotonic() - t0

        t0 = time.monotonic()
        p_out = pdfium.extract(data, text_pages)
        p_time += time.monotonic() - t0

        for page in text_pages:
            d_page = "".join(e.text for e in d_out.get(page, []))
            p_page = "".join(e.text for e in p_out.get(page, []))
            d_chars += len(d_page)
            p_chars += len(p_page)
            # The failure that mattered in production: Docling returns nothing
            # for a page that demonstrably has text.
            if not d_page.strip() and p_page.strip():
                pages_docling_empty += 1

    base.status = Status.MEASURED
    base.duration_s = round(time.monotonic() - started, 2)
    base.metrics = [
        Metric(
            key="char_ratio",
            label="Docling text vs pypdfium2",
            value=round(d_chars / p_chars, 3) if p_chars else None,
            unit="ratio",
            sample_size=pages_total,
            detail=f"{d_chars} vs {p_chars} characters over {pages_total} pages",
        ),
        Metric(
            key="pages_lost",
            label="Pages Docling returned empty",
            value=float(pages_docling_empty),
            unit="pages",
            higher_is_better=False,
            sample_size=pages_total,
            detail="pages with a real text layer that Docling read as nothing",
        ),
        Metric(
            key="docling_seconds",
            label="Docling time",
            value=round(d_time, 2),
            unit="s",
            higher_is_better=False,
            sample_size=pages_total,
        ),
        Metric(
            key="pdfium_seconds",
            label="pypdfium2 time",
            value=round(p_time, 2),
            unit="s",
            higher_is_better=False,
            sample_size=pages_total,
        ),
    ]
    return base
