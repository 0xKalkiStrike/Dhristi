"""Rule-based, explainable traffic-event detectors.

Every event carries a human-readable ``reason`` describing exactly why it fired.
No speculative behavioural inference — only geometric / kinematic rules.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from app.ai.speed.estimator import SpeedMeasurement
from app.ai.tracking.base import TrackState


@dataclass
class TrafficEventData:
    event_type: str
    severity: str
    confidence: float
    reason: str
    tracking_id: Optional[str] = None
    vehicle_class: str = "unknown"
    details: dict = field(default_factory=dict)


class EventEngine:
    """Holds per-camera rule configuration and streaming detector state."""

    def __init__(self, *, allowed_direction: Optional[str] = None,
                 stopped_frames: int = 20, dwell_frames: int = 200,
                 congestion_threshold: int = 12, restricted_zone: Optional[list] = None):
        self.allowed_direction = allowed_direction  # 'up'|'down'|'left'|'right'
        self.stopped_frames = stopped_frames
        self.dwell_frames = dwell_frames
        self.congestion_threshold = congestion_threshold
        self.restricted_zone = restricted_zone
        self._stopped_counter: dict[str, int] = {}
        self._dwell_start: dict[str, int] = {}
        self._fired: set[str] = set()  # dedupe key = f"{type}:{track}"

    def _once(self, key: str) -> bool:
        if key in self._fired:
            return False
        self._fired.add(key)
        return True

    # ---- individual rules ----
    def check_overspeed(self, track: TrackState, measure: SpeedMeasurement) -> Optional[TrafficEventData]:
        if not measure.is_violation:
            return None
        if not self._once(f"overspeed:{track.track_id}"):
            return None
        sev = "critical" if measure.excess_kmh > 25 else "warning"
        return TrafficEventData(
            event_type="overspeed", severity=sev, confidence=measure.confidence,
            reason=f"Estimated speed {measure.speed_kmh:.1f} km/h exceeds limit {measure.speed_limit_kmh:.0f} km/h "
                   f"by {measure.excess_kmh:.1f} km/h",
            tracking_id=track.track_id, vehicle_class=track.vehicle_class,
            details=measure.to_dict(),
        )

    def check_wrong_way(self, track: TrackState) -> Optional[TrafficEventData]:
        if not self.allowed_direction or len(track.trajectory) < 8:
            return None
        vx, vy = track.velocity
        if abs(vx) < 1 and abs(vy) < 1:
            return None
        moving = self._direction(vx, vy)
        if moving and moving != self.allowed_direction and _opposite(moving, self.allowed_direction):
            if not self._once(f"wrong_way:{track.track_id}"):
                return None
            return TrafficEventData(
                event_type="wrong_way", severity="critical", confidence=0.75,
                reason=f"Vehicle moving '{moving}' against allowed direction '{self.allowed_direction}'",
                tracking_id=track.track_id, vehicle_class=track.vehicle_class,
                details={"moving": moving, "allowed": self.allowed_direction},
            )
        return None

    def check_stopped(self, track: TrackState) -> Optional[TrafficEventData]:
        vx, vy = track.velocity
        speed_px = math.hypot(vx, vy)
        if speed_px < 1.2 and track.confirmed:
            self._stopped_counter[track.track_id] = self._stopped_counter.get(track.track_id, 0) + 1
        else:
            self._stopped_counter[track.track_id] = 0
        if self._stopped_counter.get(track.track_id, 0) == self.stopped_frames:
            return TrafficEventData(
                event_type="stopped_vehicle", severity="warning", confidence=0.7,
                reason=f"Vehicle stationary for {self.stopped_frames} consecutive frames",
                tracking_id=track.track_id, vehicle_class=track.vehicle_class,
            )
        return None

    def check_dwell(self, track: TrackState, frame_id: int) -> Optional[TrafficEventData]:
        self._dwell_start.setdefault(track.track_id, frame_id)
        dwell = frame_id - self._dwell_start[track.track_id]
        if dwell == self.dwell_frames:
            return TrafficEventData(
                event_type="abnormal_dwell", severity="info", confidence=0.6,
                reason=f"Vehicle present for {dwell} frames (dwell threshold reached)",
                tracking_id=track.track_id, vehicle_class=track.vehicle_class,
            )
        return None

    def check_restricted_zone(self, track: TrackState) -> Optional[TrafficEventData]:
        if not self.restricted_zone:
            return None
        if _point_in_polygon(track.center, self.restricted_zone):
            if not self._once(f"restricted:{track.track_id}"):
                return None
            return TrafficEventData(
                event_type="restricted_zone", severity="warning", confidence=0.8,
                reason="Vehicle entered a configured restricted zone",
                tracking_id=track.track_id, vehicle_class=track.vehicle_class,
            )
        return None

    def check_congestion(self, camera_id: str, active_count: int, frame_id: int) -> Optional[TrafficEventData]:
        if active_count >= self.congestion_threshold:
            key = f"congestion:{camera_id}:{frame_id // 150}"  # throttle
            if self._once(key):
                return TrafficEventData(
                    event_type="congestion", severity="warning", confidence=0.65,
                    reason=f"{active_count} active vehicles exceed congestion threshold {self.congestion_threshold}",
                    details={"active_count": active_count},
                )
        return None

    @staticmethod
    def _direction(vx: float, vy: float) -> Optional[str]:
        if abs(vx) >= abs(vy):
            return "right" if vx > 0 else "left"
        return "down" if vy > 0 else "up"


def _opposite(a: str, b: str) -> bool:
    return {"up", "down"} == {a, b} or {"left", "right"} == {a, b}


def _point_in_polygon(point, polygon) -> bool:
    if not polygon or len(polygon) < 3:
        return False
    x, y = point
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi):
            inside = not inside
        j = i
    return inside
