"""Show exactly what the reader ladder did to one PDF, page by page.

Runs the SAME `get_ladder()` the API uses, so what you see here is what an upload
would produce — no separate code path to drift out of sync.

    python -m uv run --project apps/api python tools/inspect_pdf.py "C:\\path\\to\\tender.pdf"
    python -m uv run --project apps/api python tools/inspect_pdf.py tender.pdf --pages 1-5
    python -m uv run --project apps/api python tools/inspect_pdf.py tender.pdf --text

Reads nothing from the database and writes nothing anywhere: safe to run on a
tender mid-demo.
"""

import argparse
import io
import sys
import time
from pathlib import Path

# Windows consoles default to cp1252, which cannot encode Devanagari — and a
# government tender is full of it. Without this the script dies on its own
# output rather than on anything real.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def parse_page_range(spec: str | None, total: int) -> list[int] | None:
    """"1-5" / "3" / "2,7,9" -> page numbers, or None for every page."""
    if not spec:
        return None
    wanted: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            first, last = part.split("-", 1)
            wanted.update(range(int(first), int(last) + 1))
        elif part:
            wanted.add(int(part))
    return sorted(n for n in wanted if 1 <= n <= total)


def slice_pdf(data: bytes, pages: list[int]) -> bytes:
    """A new PDF holding just `pages`, so a 283-page tender can be sampled."""
    import pypdfium2 as pdfium

    source = pdfium.PdfDocument(data)
    out = pdfium.PdfDocument.new()
    out.import_pages(source, [n - 1 for n in pages])
    buffer = io.BytesIO()
    out.save(buffer)
    return buffer.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", help="path to the PDF")
    parser.add_argument(
        "--pages", help='which pages, e.g. "1-5" or "2,7". Default: all')
    parser.add_argument(
        "--text", action="store_true", help="print sample text from every page")
    parser.add_argument(
        "--samples", type=int, default=3, help="elements to show per page (default 3)")
    args = parser.parse_args()

    path = Path(args.pdf).expanduser()
    if not path.is_file():
        print(f"not a file: {path}")
        return 1
    data = path.read_bytes()

    from bidproof_parser.ladder import inspect_pages

    from app.parsing import get_ladder

    # ---- Step 0: is each page real text, or a picture? --------------------
    infos = inspect_pages(data)
    selected = parse_page_range(args.pages, len(infos))
    if selected:
        data = slice_pdf(data, selected)
        infos = inspect_pages(data)

    ladder = get_ladder()
    threshold = ladder._min_chars

    print(f"file      : {path.name}  ({len(data):,} bytes)")
    if selected:
        print(f"pages     : {selected} (sliced from the original)")
    print(f"text step : {type(ladder._text_extractor).__name__}")
    print(f"ocr  step : {type(ladder._ocr_engine).__name__}")
    print(f"routing   : a page needs >= {threshold} characters to count as text")
    print()

    print("STEP 0 — routing decision (pypdfium2 counts the text layer)")
    print(f"  {'page':>5}  {'chars':>7}  {'size':>12}  route")
    for info in infos:
        route = "TEXT" if info.char_count >= threshold else "OCR (looks scanned)"
        print(
            f"  {info.page_no:>5}  {info.char_count:>7}  "
            f"{info.width:>5.0f}x{info.height:<6.0f}  {route}"
        )
    print()

    # ---- Steps 1-3: run the real ladder ----------------------------------
    print("running the ladder…")
    started = time.time()
    result = ladder.parse(data)
    elapsed = time.time() - started
    print()

    print(f"RESULT — {elapsed:.1f}s")
    print(f"  {'page':>5}  {'route':>5}  {'status':>8}  {'conf':>5}  "
          f"{'elements':>8}  {'dropped':>7}")
    for page in result.pages:
        print(
            f"  {page.page_no:>5}  {page.route.value:>5}  {page.status.value:>8}  "
            f"{page.confidence:>5.2f}  {len(page.elements):>8}  {page.discarded:>7}"
        )
    print()

    print("TOTALS")
    print(f"  pages          : {result.pages_total}")
    print(f"  read as text   : {result.pages_text}")
    print(f"  read by OCR    : {result.pages_ocr}")
    print(f"  flagged        : {result.pages_flagged}  <- a human must look")
    print(f"  elements       : {sum(len(p.elements) for p in result.pages)}")
    print(f"  dropped        : {result.elements_discarded}  "
          f"<- no text, no box, or no confidence: thrown away, never guessed")
    print(f"  needs a human  : {result.needs_human}")
    if getattr(ladder, "pages_recovered_by_pdfium", 0):
        print(f"  recovered      : {ladder.pages_recovered_by_pdfium} page(s) the "
              "text engine lost, re-read from the text layer instead of OCR")
    if getattr(ladder, "text_extractor_fell_back", False):
        print("  NOTE           : the text engine failed; pdfium took over")

    # ---- What it actually read -------------------------------------------
    if args.text:
        print()
        print("SAMPLE TEXT — every element carries its page and box, which is what")
        print("click-to-proof draws on. No box means it does not exist.")
        for page in result.pages:
            print(f"\n  --- page {page.page_no} ({page.route.value}) ---")
            if not page.elements:
                print("      (nothing read)")
            for element in page.elements[: args.samples]:
                box = element.bbox
                print(
                    f"      [{box.x0:.0f},{box.y0:.0f} {box.x1:.0f},{box.y1:.0f}] "
                    f"conf={element.confidence:.2f}  {element.text[:78]!r}"
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
