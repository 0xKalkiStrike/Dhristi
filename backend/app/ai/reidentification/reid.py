"""Lightweight vehicle appearance descriptor & re-identification.

Uses an HSV colour histogram signature (fast, no extra model) plus a dominant
colour label. Cross-camera association combines this appearance similarity with
plate, class, direction and temporal signals — never appearance alone.
"""
from __future__ import annotations

import cv2
import numpy as np

_COLOR_BINS = [
    ("red", [(0, 10), (170, 180)]),
    ("orange", [(11, 20)]),
    ("yellow", [(21, 33)]),
    ("green", [(34, 85)]),
    ("cyan", [(86, 100)]),
    ("blue", [(101, 130)]),
    ("purple", [(131, 160)]),
]


def dominant_color(crop: np.ndarray) -> str:
    if crop is None or crop.size == 0:
        return "unknown"
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    mean_s = float(np.mean(s))
    mean_v = float(np.mean(v))
    if mean_v < 50:
        return "black"
    if mean_s < 40 and mean_v > 180:
        return "white"
    if mean_s < 45:
        return "silver" if mean_v > 110 else "gray"
    hist = cv2.calcHist([hsv], [0], None, [180], [0, 180]).flatten()
    dom = int(np.argmax(hist))
    for name, ranges in _COLOR_BINS:
        for lo, hi in ranges:
            if lo <= dom <= hi:
                return name
    return "unknown"


def appearance_signature(crop: np.ndarray) -> dict:
    """Return a compact, serialisable appearance descriptor."""
    if crop is None or crop.size == 0:
        return {"hist": [], "color": "unknown"}
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [12, 12], [0, 180, 0, 256])
    cv2.normalize(hist, hist)
    return {"hist": hist.flatten().tolist(), "color": dominant_color(crop)}


def similarity(sig_a: dict, sig_b: dict) -> float:
    """Histogram correlation similarity in [0,1]."""
    ha, hb = sig_a.get("hist"), sig_b.get("hist")
    if not ha or not hb or len(ha) != len(hb):
        return 0.0
    a = np.array(ha, dtype=np.float32)
    b = np.array(hb, dtype=np.float32)
    corr = cv2.compareHist(a, b, cv2.HISTCMP_CORREL)
    return float(max(0.0, min(1.0, corr)))
