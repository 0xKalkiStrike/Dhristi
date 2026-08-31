"""Speed estimation from vehicle trajectories using a scene calibration."""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Optional

from app.ai.speed.calibration import Calibration
from app.ai.speed import formulas
from app.core.logging_config import get_logger

logger = get_logger("drishti.ai.speed")


@dataclass
class SpeedMeasurement:
    speed_kmh: float
    distance_m: float
    elapsed_s: float
    method: str
    confidence: float
    speed_limit_kmh: float
    excess_kmh: float
    is_violation: bool
    calibration_id: Optional[int] = None
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "speed_kmh": round(self.speed_kmh, 2),
            "distance_m": round(self.distance_m, 2),
            "elapsed_s": round(self.elapsed_s, 3),
            "method": self.method,
            "confidence": round(self.confidence, 3),
            "speed_limit_kmh": self.speed_limit_kmh,
            "excess_kmh": round(self.excess_kmh, 2),
            "is_violation": self.is_violation,
            "details": self.details,
        }


class SpeedEstimator:
    """Computes speed for tracks against a single camera calibration."""

    def __init__(self, calibration: Optional[Calibration], min_confidence: float = 0.5):
        self.cal = calibration
        self.min_confidence = min_confidence
        # streaming crossing state per track_id
        self._cross: dict[str, dict] = {}
        self._homography_samples: dict[str, list] = {}
        self._emitted: set[str] = set()

    @property
    def available(self) -> bool:
        return self.cal is not None and self.cal.is_valid

    # ---------- streaming update ----------
    def update(self, track_id: str, center: tuple[float, float], t_epoch: float) -> Optional[SpeedMeasurement]:
        if not self.available or track_id in self._emitted:
            return None
        if self.cal.method == "dual_line":
            return self._update_dual_line(track_id, center, t_epoch)
        if self.cal.method == "homography":
            return self._update_homography(track_id, center, t_epoch)
        return None

    def _update_dual_line(self, track_id, center, t_epoch) -> Optional[SpeedMeasurement]:
        st = self._cross.setdefault(track_id, {"prev_a": None, "prev_b": None, "prev_t": None, "t_a": None, "t_b": None})
        sa = self.cal.side_a(center)
        sb = self.cal.side_b(center)
        # detect zero-crossing of the signed side with sub-frame temporal interpolation (critical for 100+ km/h vehicles)
        if st["prev_a"] is not None and st["t_a"] is None and _sign_changed(st["prev_a"], sa):
            prev_t = st["prev_t"] if st["prev_t"] is not None else t_epoch
            denom = abs(st["prev_a"]) + abs(sa)
            frac = abs(st["prev_a"]) / (denom + 1e-7) if denom > 0 else 0.5
            st["t_a"] = prev_t + frac * (t_epoch - prev_t)
        if st["prev_b"] is not None and st["t_b"] is None and _sign_changed(st["prev_b"], sb):
            prev_t = st["prev_t"] if st["prev_t"] is not None else t_epoch
            denom = abs(st["prev_b"]) + abs(sb)
            frac = abs(st["prev_b"]) / (denom + 1e-7) if denom > 0 else 0.5
            st["t_b"] = prev_t + frac * (t_epoch - prev_t)
        st["prev_a"], st["prev_b"], st["prev_t"] = sa, sb, t_epoch

        if st["t_a"] is not None and st["t_b"] is not None:
            elapsed = abs(st["t_b"] - st["t_a"])
            self._emitted.add(track_id)
            return self._build(self.cal.real_distance_m, elapsed, "Calibrated dual-line crossing",
                               confidence=self._dual_line_conf(elapsed),
                               details={"line_a_time": st["t_a"], "line_b_time": st["t_b"]})
        return None

    def _update_homography(self, track_id, center, t_epoch) -> Optional[SpeedMeasurement]:
        samples = self._homography_samples.setdefault(track_id, [])
        samples.append((t_epoch, center))
        if len(samples) < 6:
            return None
        # compute windowed instantaneous speeds
        speeds = []
        total_dist = 0.0
        for (t0, p0), (t1, p1) in zip(samples[-8:-1], samples[-7:]):
            dt = t1 - t0
            d = self.cal.world_distance(p0, p1)
            if d is None or dt <= 0:
                continue
            speeds.append(formulas.mps_to_kmh(d / dt))
            total_dist += d
        if len(speeds) < 3:
            return None
        med = statistics.median(speeds)
        elapsed = samples[-1][0] - samples[-8][0] if len(samples) >= 8 else samples[-1][0] - samples[0][0]
        self._emitted.add(track_id)
        conf = self._homography_conf(speeds)
        return self._build(total_dist, max(elapsed, 1e-6), "Perspective homography", confidence=conf,
                           speed_override=med,
                           details={"samples": len(samples), "instant_speeds": [round(s, 1) for s in speeds]})

    # ---------- batch ----------
    def estimate_from_track(self, trajectory: list[tuple]) -> Optional[SpeedMeasurement]:
        """trajectory: list of (frame, t_epoch, cx, cy)."""
        if not self.available or len(trajectory) < 2:
            return None
        if self.cal.method == "dual_line":
            return self._batch_dual_line(trajectory)
        return self._batch_homography(trajectory)

    def _batch_dual_line(self, trajectory) -> Optional[SpeedMeasurement]:
        t_a = t_b = None
        prev_c = None
        prev_t = None
        for _, t, cx, cy in trajectory:
            c = (cx, cy)
            if prev_c is not None and prev_t is not None:
                if t_a is None and _sign_changed(self.cal.side_a(prev_c), self.cal.side_a(c)):
                    sa1, sa2 = self.cal.side_a(prev_c), self.cal.side_a(c)
                    denom = abs(sa1) + abs(sa2)
                    frac = abs(sa1) / (denom + 1e-7) if denom > 0 else 0.5
                    t_a = prev_t + frac * (t - prev_t)
                if t_b is None and _sign_changed(self.cal.side_b(prev_c), self.cal.side_b(c)):
                    sb1, sb2 = self.cal.side_b(prev_c), self.cal.side_b(c)
                    denom = abs(sb1) + abs(sb2)
                    frac = abs(sb1) / (denom + 1e-7) if denom > 0 else 0.5
                    t_b = prev_t + frac * (t - prev_t)
            prev_c = c
            prev_t = t
        if t_a is None or t_b is None:
            return None
        elapsed = abs(t_b - t_a)
        return self._build(self.cal.real_distance_m, elapsed, "Calibrated dual-line crossing",
                           confidence=self._dual_line_conf(elapsed),
                           details={"line_a_time": t_a, "line_b_time": t_b})

    def _batch_homography(self, trajectory) -> Optional[SpeedMeasurement]:
        speeds, total = [], 0.0
        for (_, t0, x0, y0), (_, t1, x1, y1) in zip(trajectory, trajectory[1:]):
            dt = t1 - t0
            d = self.cal.world_distance((x0, y0), (x1, y1))
            if d is None or dt <= 0:
                continue
            speeds.append(formulas.mps_to_kmh(d / dt))
            total += d
        if len(speeds) < 2:
            return None
        med = statistics.median(speeds)
        elapsed = trajectory[-1][1] - trajectory[0][1]
        return self._build(total, max(elapsed, 1e-6), "Perspective homography",
                           confidence=self._homography_conf(speeds), speed_override=med,
                           details={"instant_speeds": [round(s, 1) for s in speeds]})

    # ---------- helpers ----------
    def _build(self, distance_m, elapsed_s, method, confidence, details=None, speed_override=None) -> Optional[SpeedMeasurement]:
        try:
            spd = speed_override if speed_override is not None else formulas.speed_kmh(distance_m, elapsed_s)
        except formulas.SpeedComputationError as exc:
            logger.warning("speed computation skipped: %s", exc)
            return None
        limit = self.cal.speed_limit_kmh
        excess = formulas.excess_kmh(spd, limit)
        return SpeedMeasurement(
            speed_kmh=spd, distance_m=distance_m, elapsed_s=elapsed_s, method=method,
            confidence=confidence, speed_limit_kmh=limit, excess_kmh=excess,
            is_violation=formulas.is_violation(spd, limit), calibration_id=self.cal.calibration_id,
            details=details or {},
        )

    @staticmethod
    def _dual_line_conf(elapsed: float) -> float:
        # extremely short elapsed => less reliable timing; clamp to sane band
        if elapsed <= 0:
            return 0.0
        base = 0.94
        if elapsed < 0.15:
            base -= 0.25
        return round(min(0.97, base), 3)

    @staticmethod
    def _homography_conf(speeds: list[float]) -> float:
        if len(speeds) < 2:
            return 0.5
        mean = statistics.mean(speeds)
        if mean <= 0:
            return 0.5
        cv = statistics.pstdev(speeds) / mean  # coefficient of variation
        return round(float(max(0.5, min(0.95, 0.95 - cv))), 3)


def _sign_changed(a: float, b: float) -> bool:
    return (a <= 0 <= b) or (a >= 0 >= b)
