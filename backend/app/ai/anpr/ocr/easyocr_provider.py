"""EasyOCR provider (installed by default in this environment)."""
from __future__ import annotations

import threading

import numpy as np

from app.ai.anpr.ocr.base import OCRProvider, OCRResult
from app.core.logging_config import get_logger

logger = get_logger("drishti.ai.ocr.easyocr")

_ALLOWLIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


class EasyOCRProvider(OCRProvider):
    name = "easyocr"

    def __init__(self, gpu: bool = False):
        self._gpu = gpu
        self._reader = None
        self._lock = threading.Lock()
        self._ok = None  # lazily determined

    def _ensure(self) -> bool:
        if self._reader is not None:
            return True
        if self._ok is False:
            return False
        with self._lock:
            if self._reader is not None:
                return True
            try:
                import easyocr
                self._reader = easyocr.Reader(["en"], gpu=self._gpu, verbose=False)
                self._ok = True
                logger.info("EasyOCR reader initialised", extra={"extra_fields": {"gpu": self._gpu}})
            except Exception as exc:  # pragma: no cover
                logger.error("EasyOCR init failed: %s", exc)
                self._ok = False
        return bool(self._ok)

    @property
    def available(self) -> bool:
        try:
            import easyocr  # noqa: F401
            return True
        except Exception:
            return False

    def read_text(self, image: np.ndarray) -> OCRResult:
        if image is None or not self._ensure():
            return OCRResult("", 0.0, self.name)
        try:
            results = self._reader.readtext(image, allowlist=_ALLOWLIST, detail=1, paragraph=False)
        except Exception as exc:
            logger.warning("EasyOCR read failed: %s", exc)
            return OCRResult("", 0.0, self.name)
        if not results:
            return OCRResult("", 0.0, self.name)
        # Sort detected boxes top-to-bottom (grouped by vertical rows) then left-to-right
        results.sort(key=lambda r: (round(r[0][0][1] / 25), r[0][0][0]))
        text = "".join(r[1] for r in results)
        confs = [float(r[2]) for r in results if r[2] is not None]
        conf = sum(confs) / len(confs) if confs else 0.0
        return OCRResult(text=text, confidence=conf, engine=self.name)
