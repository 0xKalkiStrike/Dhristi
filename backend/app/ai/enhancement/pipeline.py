"""Adaptive enhancement pipeline.

Selects preprocessing based on the environment analysis. The ORIGINAL frame is
always preserved; enhancement is only applied when the quality report indicates
it should help. Callers may compare detector confidence on original vs enhanced
frames and keep whichever is better (never assume enhancement wins).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.ai.enhancement import enhancers
from app.ai.environment.classifier import QualityReport
from app.core.config import settings


@dataclass
class EnhancementResult:
    frame: np.ndarray
    applied: list[str]
    changed: bool


class AdaptiveEnhancer:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def enhance(self, frame: np.ndarray, report: QualityReport) -> EnhancementResult:
        if not self.enabled or frame is None:
            return EnhancementResult(frame=frame, applied=[], changed=False)

        applied: list[str] = []
        out = frame
        env = report.environment

        if env == "fog":
            out = enhancers.dehaze(out)
            out = enhancers.apply_clahe(out, clip=2.5)
            applied += ["dehaze", "clahe"]
        elif env == "night":
            out = enhancers.low_light_enhance(out)
            out = enhancers.denoise(out, strength=4)
            applied += ["gamma", "clahe", "denoise"]
        elif env == "low_light":
            out = enhancers.gamma_correct(out, gamma=1.5)
            out = enhancers.apply_clahe(out, clip=2.0)
            applied += ["gamma", "clahe"]
        elif env == "overexposed":
            out = enhancers.gamma_correct(out, gamma=0.7)
            applied += ["gamma_down"]
        elif env == "blur":
            out = enhancers.sharpen(out, amount=0.8)
            applied += ["sharpen"]
        else:
            # daytime / normal: keep original
            return EnhancementResult(frame=frame, applied=[], changed=False)

        return EnhancementResult(frame=out, applied=applied, changed=True)


def build_enhancer() -> AdaptiveEnhancer:
    return AdaptiveEnhancer(enabled=settings.enhancement_enabled)
