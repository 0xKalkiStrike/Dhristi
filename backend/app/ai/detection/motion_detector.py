"""Classical-CV motion detector (real computer vision, no deep model).

Uses MOG2 background subtraction + contour analysis. This is a genuine CV
technique — NOT fabricated results. It is used as a transparent fallback when
no deep model is loaded, and for the deterministic synthetic demo video (where
abstract 'vehicle' blobs are not recognisable to COCO models). The UI always
labels the active backend so operators know a classical detector is in use.
"""
from __future__ import annotations

import cv2
import numpy as np

from app.ai.detection.base import Detection, VehicleDetector
from app.core.logging_config import get_logger

logger = get_logger("drishti.ai.motion")


class MotionDetector(VehicleDetector):
    name = "motion"
    is_deep_model = False

    def __init__(self, min_area: int = 900, confidence_floor: float = 0.4):
        self.min_area = min_area
        self.confidence_floor = confidence_floor
        self._bg = cv2.createBackgroundSubtractorMOG2(history=200, varThreshold=32, detectShadows=True)
        self._kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

    def _classify(self, w: float, h: float) -> str:
        area = w * h
        ar = w / h if h > 0 else 1.0
        if area < 2500 and ar < 1.3:
            return "motorcycle"
        if area > 22000 or (ar > 2.4 and area > 12000):
            return "truck"
        if area > 14000 and ar > 1.6:
            return "bus"
        return "car"

    def detect(self, frame: np.ndarray, camera_id: str = "", frame_id: int = 0) -> list[Detection]:
        if frame is None:
            return []
        mask = self._bg.apply(frame)
        # remove shadows (grey=127) and denoise
        _, mask = cv2.threshold(mask, 200, 255, cv2.THRESH_BINARY)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self._kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self._kernel, iterations=2)
        mask = cv2.dilate(mask, self._kernel, iterations=1)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        h_img, w_img = frame.shape[:2]
        frame_area = float(h_img * w_img)
        dets: list[Detection] = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < self.min_area:
                continue
            x, y, w, h = cv2.boundingRect(c)
            if w < 12 or h < 12:
                continue
            # confidence proportional to how solid the blob is
            solidity = area / float(w * h + 1e-6)
            size_factor = min(1.0, (w * h) / (frame_area * 0.15))
            conf = float(np.clip(self.confidence_floor + 0.5 * solidity + 0.1 * size_factor, 0.4, 0.97))
            dets.append(
                Detection(
                    vehicle_class=self._classify(w, h), confidence=conf,
                    bbox=(float(x), float(y), float(x + w), float(y + h)),
                    camera_id=camera_id, frame_id=frame_id,
                    extra={"backend": "motion", "solidity": round(solidity, 3)},
                )
            )
        return dets
