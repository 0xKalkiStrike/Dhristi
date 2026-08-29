"""Scene calibration for physical speed estimation.

Two supported methods:

* ``dual_line``  – two virtual lines a known real-world distance apart. Speed is
  computed from the time a vehicle centre takes to travel between them.
* ``homography`` – a perspective transform from image pixels to a metric ground
  plane (4 image points ↔ 4 world points in metres). Speed is computed from the
  metric displacement between trajectory samples.

Both are genuine photogrammetric techniques. Without calibration the estimator
declines to produce a value (rather than fabricating one).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np


def _line_side(p: tuple, a: tuple, b: tuple) -> float:
    """Signed side of point p relative to line a->b (>0 one side, <0 other)."""
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


@dataclass
class Calibration:
    method: str = "dual_line"
    line_a: Optional[list] = None       # [[x1,y1],[x2,y2]]
    line_b: Optional[list] = None
    real_distance_m: float = 0.0
    image_points: Optional[list] = None  # 4x[x,y]
    world_points: Optional[list] = None  # 4x[x,y] metres
    speed_limit_kmh: float = 60.0
    calibration_id: Optional[int] = None
    _H: Optional[np.ndarray] = None

    def __post_init__(self):
        if self.method == "homography":
            self._compute_homography()

    # ---- validity ----
    @property
    def is_valid(self) -> bool:
        if self.method == "dual_line":
            return bool(self.line_a) and bool(self.line_b) and self.real_distance_m > 0
        if self.method == "homography":
            return self._H is not None
        return False

    def _compute_homography(self) -> None:
        if not self.image_points or not self.world_points:
            self._H = None
            return
        if len(self.image_points) < 4 or len(self.world_points) < 4:
            self._H = None
            return
        src = np.array(self.image_points[:4], dtype=np.float64)
        dst = np.array(self.world_points[:4], dtype=np.float64)
        try:
            import cv2
            H, _ = cv2.findHomography(src, dst)
            self._H = H
        except Exception:
            self._H = None

    # ---- homography world mapping ----
    def image_to_world(self, point: tuple[float, float]) -> Optional[tuple[float, float]]:
        if self._H is None:
            return None
        px = np.array([point[0], point[1], 1.0], dtype=np.float64)
        w = self._H @ px
        if abs(w[2]) < 1e-9:
            return None
        return (float(w[0] / w[2]), float(w[1] / w[2]))

    def world_distance(self, p1: tuple, p2: tuple) -> Optional[float]:
        w1 = self.image_to_world(p1)
        w2 = self.image_to_world(p2)
        if w1 is None or w2 is None:
            return None
        return math.hypot(w2[0] - w1[0], w2[1] - w1[1])

    # ---- dual-line crossing ----
    def side_a(self, point: tuple) -> float:
        return _line_side(point, tuple(self.line_a[0]), tuple(self.line_a[1]))

    def side_b(self, point: tuple) -> float:
        return _line_side(point, tuple(self.line_b[0]), tuple(self.line_b[1]))

    @classmethod
    def from_orm(cls, cal) -> "Calibration":
        return cls(
            method=cal.method,
            line_a=cal.line_a, line_b=cal.line_b, real_distance_m=cal.real_distance_m,
            image_points=cal.image_points, world_points=cal.world_points,
            speed_limit_kmh=cal.speed_limit_kmh, calibration_id=cal.id,
        )
