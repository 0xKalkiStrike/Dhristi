"""Tesseract OCR provider (requires the tesseract binary to be installed)."""
from __future__ import annotations

import numpy as np

from app.ai.anpr.ocr.base import OCRProvider, OCRResult
from app.core.logging_config import get_logger

logger = get_logger("drishti.ai.ocr.tesseract")

_CONFIG = "--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


class TesseractProvider(OCRProvider):
    name = "tesseract"

    def __init__(self):
        self._ok = None

    @property
    def available(self) -> bool:
        if self._ok is not None:
            return self._ok
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            self._ok = True
        except Exception as exc:
            logger.info("tesseract binary unavailable: %s", exc)
            self._ok = False
        return self._ok

    def read_text(self, image: np.ndarray) -> OCRResult:
        if image is None or not self.available:
            return OCRResult("", 0.0, self.name)
        try:
            import pytesseract
            from pytesseract import Output
            data = pytesseract.image_to_data(image, config=_CONFIG, output_type=Output.DICT)
        except Exception as exc:
            logger.warning("tesseract read failed: %s", exc)
            return OCRResult("", 0.0, self.name)
        parts, confs = [], []
        for txt, conf in zip(data["text"], data["conf"]):
            if txt and txt.strip():
                parts.append(txt.strip())
                try:
                    c = float(conf)
                    if c >= 0:
                        confs.append(c / 100.0)
                except (TypeError, ValueError):
                    pass
        text = "".join(parts)
        conf = sum(confs) / len(confs) if confs else 0.0
        return OCRResult(text=text, confidence=conf, engine=self.name)
