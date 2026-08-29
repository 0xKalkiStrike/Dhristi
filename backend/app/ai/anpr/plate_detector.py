"""Classical number-plate region detector.

No dedicated plate-detection deep model ships with this environment, so we locate
candidate plate regions inside a vehicle crop using edge density, morphology and
aspect-ratio filtering — a standard, explainable ANPR front-end. Candidates are
ranked; the ANPR pipeline OCRs the best one(s).
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class PlateCandidate:
    bbox: tuple[int, int, int, int]   # x1,y1,x2,y2 relative to input image
    score: float
    crop: np.ndarray


class PlateDetector:
    def __init__(self, min_area: int = 250, min_aspect: float = 0.7, max_aspect: float = 6.5):
        self.min_area = min_area
        self.min_aspect = min_aspect
        self.max_aspect = max_aspect

    def detect(self, image: np.ndarray, max_candidates: int = 4) -> list[PlateCandidate]:
        if image is None or image.size == 0:
            return []
        h, w = image.shape[:2]
        if h < 20 or w < 20:
            return []
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        gray_blur = cv2.bilateralFilter(gray, 7, 17, 17)
        # Emphasise horizontal edge structure typical of plates
        edges = cv2.Sobel(gray_blur, cv2.CV_8U, 1, 0, ksize=3)
        _, thresh = cv2.threshold(edges, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (13, 5))
        morph = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        morph = cv2.dilate(morph, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)), iterations=1)

        contours, _ = cv2.findContours(morph, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates: list[PlateCandidate] = []
        for c in contours:
            x, y, cw, ch = cv2.boundingRect(c)
            area = cw * ch
            if area < self.min_area or ch == 0:
                continue
            aspect = cw / float(ch)
            if not (self.min_aspect <= aspect <= self.max_aspect):
                continue
            # Plates typically sit in the lower half of a vehicle
            vertical_bias = (y + ch / 2) / h
            edge_density = float(np.count_nonzero(morph[y:y + ch, x:x + cw])) / (area + 1e-6)
            score = edge_density * (0.5 + 0.5 * vertical_bias)
            pad = 4
            x1, y1 = max(0, x - pad), max(0, y - pad)
            x2, y2 = min(w, x + cw + pad), min(h, y + ch + pad)
            crop = image[y1:y2, x1:x2].copy()
            candidates.append(PlateCandidate(bbox=(x1, y1, x2, y2), score=float(score), crop=crop))

        # Also add a candidate for the lower-center portion of the vehicle (standard plate zone)
        ly1 = int(h * 0.35)
        ly2 = int(h * 0.98)
        lx1 = int(w * 0.05)
        lx2 = int(w * 0.95)
        if ly2 > ly1 and lx2 > lx1:
            lower_crop = image[ly1:ly2, lx1:lx2].copy()
            candidates.append(PlateCandidate(bbox=(lx1, ly1, lx2, ly2), score=0.65, crop=lower_crop))

        # Full vehicle crop fallback (in case plate takes up most of tight crop)
        candidates.append(PlateCandidate(bbox=(0, 0, w, h), score=0.5, crop=image.copy()))

        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates[:max_candidates]

    @staticmethod
    def preprocess_for_ocr(crop: np.ndarray) -> np.ndarray:
        """Upscale + enhance plate crop for more reliable OCR (both cars & 2-wheelers)."""
        if crop is None or crop.size == 0:
            return crop
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
        h, w = gray.shape[:2]
        # Ensure minimum height for clean OCR text
        if h < 64:
            scale = 64.0 / max(1, h)
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        # Apply gentle CLAHE to bring out text contrast without harsh binary threshold destruction
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
        enhanced = clahe.apply(gray)
        return enhanced
