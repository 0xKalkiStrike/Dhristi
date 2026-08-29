"""End-to-end ANPR pipeline.

vehicle crop -> plate detection -> preprocessing -> OCR -> normalise -> validate
-> confidence scoring. Emits ``None`` when no plate is legible (never fabricates).
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from app.ai.anpr.normalizer import normalize_plate
from app.ai.anpr.ocr import OCRProvider, build_ocr_provider
from app.ai.anpr.plate_detector import PlateDetector
from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger("drishti.ai.anpr")


@dataclass
class PlateResult:
    raw_text: str
    normalized_text: str
    confidence: float
    ocr_confidence: float
    valid_format: bool
    needs_verification: bool
    ocr_engine: str
    plate_bbox: tuple[int, int, int, int]
    crop_path: str = ""

    def to_dict(self) -> dict:
        return {
            "raw_text": self.raw_text,
            "normalized_text": self.normalized_text,
            "confidence": round(self.confidence, 3),
            "valid_format": self.valid_format,
            "needs_verification": self.needs_verification,
            "ocr_engine": self.ocr_engine,
            "plate_bbox": list(self.plate_bbox),
            "crop_path": self.crop_path,
        }


class ANPRPipeline:
    def __init__(self, ocr: Optional[OCRProvider] = None):
        self.detector = PlateDetector(min_area=settings.anpr_min_plate_area)
        self.ocr = ocr or build_ocr_provider(settings.ocr_engine)
        self.min_conf = settings.ocr_min_confidence
        self.verify_conf = settings.anpr_verify_confidence

    @property
    def ocr_available(self) -> bool:
        return getattr(self.ocr, "available", False)

    def read_plate(self, vehicle_crop: np.ndarray, *, save: bool = False,
                   camera_id: str = "", tracking_id: str = "") -> Optional[PlateResult]:
        if vehicle_crop is None or vehicle_crop.size == 0:
            return None
        if not self.ocr_available:
            return None
        candidates = self.detector.detect(vehicle_crop)
        if not candidates:
            return None

        best: Optional[PlateResult] = None
        for cand in candidates:
            pre = self.detector.preprocess_for_ocr(cand.crop)
            ocr_res = self.ocr.read_text(pre)
            if not ocr_res.text or ocr_res.confidence < self.min_conf:
                continue
            norm = normalize_plate(ocr_res.text, settings.plate_country)
            # combined confidence: OCR score, boosted when the format validates
            combined = ocr_res.confidence * (1.0 if norm.valid_format else 0.75)
            result = PlateResult(
                raw_text=ocr_res.text,
                normalized_text=norm.normalized,
                confidence=round(float(combined), 3),
                ocr_confidence=round(float(ocr_res.confidence), 3),
                valid_format=norm.valid_format,
                needs_verification=(combined < self.verify_conf) or (not norm.valid_format),
                ocr_engine=ocr_res.engine,
                plate_bbox=cand.bbox,
            )
            if best is None or result.confidence > best.confidence:
                best = result
                best._crop = cand.crop  # type: ignore[attr-defined]

        if best is None:
            return None

        if save and getattr(best, "_crop", None) is not None:
            best.crop_path = self._save_crop(best._crop, camera_id, tracking_id)  # type: ignore[attr-defined]
        return best

    @staticmethod
    def _save_crop(crop: np.ndarray, camera_id: str, tracking_id: str) -> str:
        try:
            out_dir: Path = settings.outputs_dir / "plates"
            out_dir.mkdir(parents=True, exist_ok=True)
            ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = f"{camera_id or 'cam'}_{tracking_id or 'trk'}_{ts}_{uuid.uuid4().hex[:6]}.jpg"
            path = out_dir / fname
            cv2.imwrite(str(path), crop)
            return str(path.relative_to(settings.data_dir.parent)) if path.exists() else ""
        except Exception as exc:  # pragma: no cover
            logger.warning("failed to save plate crop: %s", exc)
            return ""
