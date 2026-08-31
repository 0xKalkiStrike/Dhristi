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
        
        # Temporal smoothing state to prevent filter flickering on real video shots
        self._smooth_brightness: float | None = None
        self._smooth_contrast: float | None = None
        self._smooth_fog: float | None = None
        self._smooth_lowlight: float | None = None
        self._current_label = "day"
        self._label_counts: dict[str, int] = {}

    def analyze(self, frame: np.ndarray) -> QualityReport:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        raw_brightness = float(np.mean(gray)) / 255.0
        raw_contrast = float(np.std(gray)) / 128.0
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        # Fog/haze: low contrast + high, uniform brightness + weak dark channel.
        dark_channel = self._dark_channel(frame) if frame.ndim == 3 else float(np.min(gray)) / 255.0
        raw_fog = float(np.clip((1.0 - raw_contrast) * 0.6 + dark_channel * 0.4, 0.0, 1.0))

        # Low light: darkness weighted by low contrast.
        raw_lowlight = float(np.clip((1.0 - raw_brightness) * 0.7 + (0.3 if raw_contrast < 0.15 else 0.0), 0.0, 1.0))

        # Temporal EMA smoothing (35% new measurement, 65% history) for stable visuals
        if self._smooth_brightness is None:
            self._smooth_brightness = raw_brightness
            self._smooth_contrast = raw_contrast
            self._smooth_fog = raw_fog
            self._smooth_lowlight = raw_lowlight
            cand_label = self._label(self._smooth_brightness, self._smooth_contrast, blur_score,
                                      self._smooth_fog, self._smooth_lowlight)
            self._current_label = cand_label
            self._label_counts[cand_label] = 1
        else:
            alpha = 0.35
            self._smooth_brightness = alpha * raw_brightness + (1 - alpha) * self._smooth_brightness
            self._smooth_contrast = alpha * raw_contrast + (1 - alpha) * self._smooth_contrast
            self._smooth_fog = alpha * raw_fog + (1 - alpha) * self._smooth_fog
            self._smooth_lowlight = alpha * raw_lowlight + (1 - alpha) * self._smooth_lowlight
            cand_label = self._label(self._smooth_brightness, self._smooth_contrast, blur_score,
                                      self._smooth_fog, self._smooth_lowlight)
            # Hysteresis confirmation: require sustained detection before flipping environment state
            self._label_counts[cand_label] = self._label_counts.get(cand_label, 0) + 1
            for k in list(self._label_counts.keys()):
                if k != cand_label:
                    self._label_counts[k] = max(0, self._label_counts[k] - 1)
            if self._label_counts[cand_label] >= 2:
                self._current_label = cand_label

        return QualityReport(
            environment=self._current_label,
            brightness=self._smooth_brightness,
            contrast=self._smooth_contrast,
            blur_score=blur_score,
            fog_score=self._smooth_fog,
            lowlight_score=self._smooth_lowlight,
            scores={
                "day": 1.0 - self._smooth_lowlight,
                "fog": self._smooth_fog,
                "lowlight": self._smooth_lowlight,
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
