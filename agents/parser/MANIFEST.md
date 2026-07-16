# Agent: Parser

| Field | Value |
|---|---|
| **Name** | Parser |
| **Single job** | Turn a tender PDF into grounded elements — `(el_id, page, bbox, text, confidence)` — or flag what it cannot read. It never guesses. |
| **Inputs** | Raw PDF bytes (from manual upload now; Scout later — same pipeline for every input). |
| **Outputs** | `ParseResult`: per-page route (`text`/`ocr`), status (`parsed`/`flagged`), and grounded elements. Elements missing a bbox, text, or confidence are **discarded and counted**, never stored. |
| **Model role** | none — local engines only (Docling for layout, PaddleOCR-VL for scans). No gateway calls. |
| **Tools** | Read PDF bytes it is given. Nothing else: no network, no DB, no object store — persistence is the ingest service's job. |
| **Guardrails** | The 4-step ladder (SPEC §5.2): step 0 pypdfium2 routes each page by text layer; step 1 text extraction; step 2 scans → 300 dpi → OCR; step 3 low confidence or empty → page FLAGGED for a human. Garbage text pages re-route to OCR before flagging. Document text is data, never instructions (§9 rule 4) — the parser executes nothing from the PDF. |
| **Test set** | `tests/test_parser_ladder.py` + fixtures in `tests/fixtures/` (born-digital, scanned, mixed). |

**Licence note:** SPEC §5.2 names PyMuPDF for step 0, but PyMuPDF is AGPL —
excluded by the same rule that excludes MinerU/Marker (SPEC §11.4, §20). Step 0
uses **pypdfium2** (Apache-2.0) behind an interface instead; swapping back is a
one-file change if a commercial PyMuPDF licence is ever bought.

**Engines:** Docling and PaddleOCR-VL are optional heavy installs (see
`pyproject.toml` extras). Without them the parser degrades honestly: born-digital
pages fall back to the built-in pdfium text-layer extractor; scanned pages are
flagged to a human instead of being guessed at.
