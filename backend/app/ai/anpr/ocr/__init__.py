"""OCR provider factory."""
from __future__ import annotations

from app.ai.anpr.ocr.base import OCRProvider, OCRResult
from app.core.logging_config import get_logger

logger = get_logger("drishti.ai.ocr")


def build_ocr_provider(engine: str = "easyocr", gpu: bool = False) -> OCRProvider:
    engine = (engine or "easyocr").lower()

    def _easy():
        from app.ai.anpr.ocr.easyocr_provider import EasyOCRProvider
        p = EasyOCRProvider(gpu=gpu)
        return p if p.available else None

    def _tess():
        from app.ai.anpr.ocr.tesseract_provider import TesseractProvider
        p = TesseractProvider()
        return p if p.available else None

    def _paddle():
        from app.ai.anpr.ocr.paddle_provider import PaddleOCRProvider
        p = PaddleOCRProvider(gpu=gpu)
        return p if p.available else None

    builders = {"easyocr": _easy, "tesseract": _tess, "paddleocr": _paddle}
    # try requested first, then remaining as fallback
    order = [engine] + [e for e in builders if e != engine]
    for name in order:
        p = builders[name]()
        if p:
            if name != engine:
                logger.warning("OCR engine %s unavailable; using %s", engine, name)
            return p
    logger.warning("no OCR engine available; ANPR text disabled")
    return _NullOCR()


class _NullOCR(OCRProvider):
    name = "none"

    @property
    def available(self) -> bool:
        return False

    def read_text(self, image):
        return OCRResult("", 0.0, self.name)


__all__ = ["OCRProvider", "OCRResult", "build_ocr_provider"]
