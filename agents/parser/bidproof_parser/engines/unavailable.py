from bidproof_parser.types import RawElement


class UnavailableOcrEngine:
    """Used when no OCR engine is installed. Returns nothing, so every
    OCR-routed page is FLAGGED for a human — the system degrades by asking
    for help, never by guessing (SPEC §12.2)."""

    def extract(self, pdf_bytes: bytes, page_no: int) -> list[RawElement]:
        return []
