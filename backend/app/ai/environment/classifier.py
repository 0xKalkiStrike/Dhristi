"""Image-quality / environment analysis.

Estimates lighting and visibility conditions from frame statistics so the
pipeline can adapt preprocessing. Scores are heuristic (0..1) and reported with
the environment label rather than presented as ground truth.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from app.core.config import settings


@dataclass
class QualityReport:
    environment: str
    brightness: float
    contrast: float
    blur_score: float          # variance of Laplacian (higher = sharper)
    fog_score: float           # 0..1 (higher = foggier/hazier)
    lowlight_score: float      # 0..1 (higher = darker)
    scores: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "environment": self.environment,
            "brightness": round(self.brightness, 3),
            "contrast": round(self.contrast, 3),
            "blur_score": round(self.blur_score, 2),
            "fog_score": round(self.fog_score, 3),
            "lowlight_score": round(self.lowlight_score, 3),
            "scores": {k: round(v, 3) for k, v in self.scores.items()},
        }


class ImageQualityService:
    def __init__(self):
        self.fog_thr = settings.fog_score_threshold
        self.lowlight_thr = settings.lowlight_score_threshold
        self.blur_thr = settings.blur_score_threshold

    def analyze(self, frame: np.ndarray) -> QualityReport:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        brightness = float(np.mean(gray)) / 255.0
        contrast = float(np.std(gray)) / 128.0
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        # Fog/haze: low contrast + high, uniform brightness + weak dark channel.
        dark_channel = self._dark_channel(frame) if frame.ndim == 3 else float(np.min(gray)) / 255.0
        fog_score = float(np.clip((1.0 - contrast) * 0.6 + dark_channel * 0.4, 0.0, 1.0))

        # Low light: darkness weighted by low contrast.
        lowlight_score = float(np.clip((1.0 - brightness) * 0.7 + (0.3 if contrast < 0.15 else 0.0), 0.0, 1.0))

        env = self._label(brightness, contrast, blur_score, fog_score, lowlight_score)
        return QualityReport(
            environment=env, brightness=brightness, contrast=contrast, blur_score=blur_score,
            fog_score=fog_score, lowlight_score=lowlight_score,
            scores={
                "day": 1.0 - lowlight_score,
                "fog": fog_score,
                "lowlight": lowlight_score,
                "blur": 1.0 if blur_score < self.blur_thr else 0.0,
            },
        )

    def _label(self, brightness, contrast, blur, fog, lowlight) -> str:
        if brightness > 0.88 and contrast < 0.10:
            return "overexposed"
        # Fog/haze requires low contrast, high brightness, and genuinely high fog score
        if fog >= 0.75 and brightness > 0.40 and contrast < 0.18:
            return "fog"
        if lowlight >= 0.82 and brightness < 0.18:
            return "night"
        if lowlight >= 0.75 and brightness < 0.28:
            return "low_light"
        if blur < self.blur_thr:
            return "blur"
        return "day"

    @staticmethod
    def _dark_channel(frame: np.ndarray, patch: int = 15) -> float:
        min_c = np.min(frame, axis=2)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (patch, patch))
        dark = cv2.erode(min_c, kernel)
        return float(np.mean(dark)) / 255.0
