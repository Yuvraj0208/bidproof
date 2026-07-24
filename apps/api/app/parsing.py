"""Wiring for the Parser agent (agents/parser). Picks the best installed
engine per step and degrades honestly: no Docling -> built-in pdfium text
extractor; no OCR engine -> OCR pages are flagged to a human, never guessed.

OCR preference: RapidOCR first, then PaddleOCR-VL. Both run the same PP-OCR
models; RapidOCR uses onnxruntime, which is portable to CPUs/OSes where
paddlepaddle's backend won't run (SPEC §6 note). PaddleOCR-VL remains the
fallback for environments where its backend is available.
"""

import logging
from functools import lru_cache

from bidproof_parser import ParserLadder
from bidproof_parser.engines import PdfiumTextExtractor, UnavailableOcrEngine
from bidproof_parser.engines.docling_engine import docling_available
from bidproof_parser.engines.paddle_ocr_vl import paddle_ocr_available
from bidproof_parser.engines.rapid_ocr import rapid_ocr_available

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_ladder() -> ParserLadder:
    settings = get_settings()

    if docling_available():
        from bidproof_parser.engines.docling_engine import DoclingTextExtractor

        text_extractor = DoclingTextExtractor()
    else:
        text_extractor = PdfiumTextExtractor()
        logger.info("docling not installed; using built-in pdfium text extractor")

    if rapid_ocr_available():
        from bidproof_parser.engines.rapid_ocr import RapidOcrEngine

        ocr_engine = RapidOcrEngine()
        logger.info("OCR engine: RapidOCR (onnxruntime)")
    elif paddle_ocr_available():
        from bidproof_parser.engines.paddle_ocr_vl import PaddleOcrVlEngine

        ocr_engine = PaddleOcrVlEngine()
        logger.info("OCR engine: PaddleOCR-VL (paddlepaddle)")
    else:
        ocr_engine = UnavailableOcrEngine()
        logger.info("no OCR engine installed; scan pages will be flagged to humans")

    return ParserLadder(
        text_extractor,
        ocr_engine,
        min_chars_text_page=settings.parser_min_chars_text_page,
        page_confidence_threshold=settings.parser_page_confidence_threshold,
    )
