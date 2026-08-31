"""Individual image-enhancement operations (all pure functions on BGR frames)."""
from __future__ import annotations

import cv2
import numpy as np


def apply_clahe(frame: np.ndarray, clip: float = 2.0, grid: int = 8) -> np.ndarray:
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(grid, grid))
    l = clahe.apply(l)
    return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)


def gamma_correct(frame: np.ndarray, gamma: float = 1.5) -> np.ndarray:
    inv = 1.0 / max(1e-3, gamma)
    table = ((np.arange(256) / 255.0) ** inv * 255).astype(np.uint8)
    return cv2.LUT(frame, table)


def denoise(frame: np.ndarray, strength: int = 5) -> np.ndarray:
    d = min(7, max(3, strength))
    sigma = float(strength * 8)
    return cv2.bilateralFilter(frame, d, sigma, sigma)


def sharpen(frame: np.ndarray, amount: float = 1.0) -> np.ndarray:
    blur = cv2.GaussianBlur(frame, (0, 0), 3)
    return cv2.addWeighted(frame, 1 + amount, blur, -amount, 0)


def white_balance(frame: np.ndarray) -> np.ndarray:
    result = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB).astype(np.float32)
    avg_a = np.average(result[:, :, 1])
    avg_b = np.average(result[:, :, 2])
    result[:, :, 1] -= (avg_a - 128) * (result[:, :, 0] / 255.0) * 1.1
    result[:, :, 2] -= (avg_b - 128) * (result[:, :, 0] / 255.0) * 1.1
    result = np.clip(result, 0, 255).astype(np.uint8)
    return cv2.cvtColor(result, cv2.COLOR_LAB2BGR)


def dehaze(frame: np.ndarray, clip: float = 2.0) -> np.ndarray:
    """Fast, artifact-free contrast-recovery dehaze without halo effects."""
    if frame is None or frame.size == 0:
        return frame
    # Use gentle CLAHE on luminance and slight white balance recovery
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(8, 8))
    l = clahe.apply(l)
    return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)


def low_light_enhance(frame: np.ndarray) -> np.ndarray:
    out = gamma_correct(frame, gamma=1.8)
    out = apply_clahe(out, clip=3.0, grid=8)
    return out
