"""PaddleOCR provider (optional; used when paddleocr is installed)."""
from __future__ import annotations

import numpy as np

from app.ai.anpr.ocr.base import OCRProvider, OCRResult
from app.core.logging_config import get_logger

logger = get_logger("drishti.ai.ocr.paddle")


class PaddleOCRProvider(OCRProvider):
    name = "paddleocr"

    def __init__(self, gpu: bool = False):
        self._gpu = gpu
        self._engine = None
        self._ok = None

    @property
    def available(self) -> bool:
        if self._ok is not None:
            return self._ok
        try:
            import paddleocr  # noqa: F401
            self._ok = True
        except Exception:
            self._ok = False
        return self._ok

    def _ensure(self) -> bool:
        if self._engine is not None:
            return True
        if not self.available:
            return False
        try:
            from paddleocr import PaddleOCR
            self._engine = PaddleOCR(use_angle_cls=True, lang="en", show_log=False, use_gpu=self._gpu)
            return True
        except Exception as exc:  # pragma: no cover
            logger.error("PaddleOCR init failed: %s", exc)
            self._ok = False
            return False

    def read_text(self, image: np.ndarray) -> OCRResult:
        if image is None or not self._ensure():
            return OCRResult("", 0.0, self.name)
        try:
            result = self._engine.ocr(image, cls=True)
        except Exception as exc:
            logger.warning("PaddleOCR read failed: %s", exc)
            return OCRResult("", 0.0, self.name)
        parts, confs = [], []
        for line in (result or []):
            for box in (line or []):
                txt, conf = box[1]
                parts.append(txt)
                confs.append(float(conf))
        text = "".join(parts)
        conf = sum(confs) / len(confs) if confs else 0.0
        return OCRResult(text=text, confidence=conf, engine=self.name)
