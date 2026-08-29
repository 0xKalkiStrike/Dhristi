"""Vehicle identity & cross-camera association.

Associates observations into persistent vehicle identities using multiple
signals (plate, appearance, class, time) and maintains a cross-camera journey.
Association is probabilistic and always carries a confidence score.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.reidentification import reid
from app.core.logging_config import get_logger
from app.models import Vehicle, VehicleJourney, VehicleObservation

logger = get_logger("drishti.identity")

APPEARANCE_MATCH = 0.72        # min hist similarity for cross-camera match
ASSOC_WINDOW_MIN = 30          # look back window for cross-camera association


def _uid() -> str:
    return f"VH-{uuid.uuid4().int % 1000000:06d}"


class VehicleIdentityService:
    def __init__(self, db: Session):
        self.db = db

    def resolve(self, *, camera_id: str, plate: str | None, plate_conf: float,
                appearance: dict, vehicle_class: str, color: str,
                timestamp: dt.datetime) -> tuple[str, float]:
        """Return (vehicle_uid, association_confidence)."""
        # 1) strong signal: valid plate already known
        if plate:
            existing = self.db.scalar(select(Vehicle).where(Vehicle.plate_number == plate))
            if existing:
                return existing.vehicle_uid, 0.98
        # 2) appearance + class within a recent time window (cross-camera)
        window_start = timestamp - dt.timedelta(minutes=ASSOC_WINDOW_MIN)
        recent = self.db.scalars(
            select(Vehicle).where(Vehicle.last_seen >= window_start,
                                  Vehicle.vehicle_class == vehicle_class)
            .order_by(Vehicle.last_seen.desc()).limit(50)
        ).all()
        best_uid, best_sim = None, 0.0
        for v in recent:
            sig = (v.appearance or {})
            sim = reid.similarity(sig, appearance)
            if sim > best_sim:
                best_sim, best_uid = sim, v.vehicle_uid
        if best_uid and best_sim >= APPEARANCE_MATCH:
            conf = round(0.5 + 0.45 * best_sim, 3)
            return best_uid, conf
        # 3) new identity
        return self._create(plate, plate_conf, appearance, vehicle_class, color, timestamp), 1.0

    def _create(self, plate, plate_conf, appearance, vehicle_class, color, ts) -> str:
        uid = _uid()
        v = Vehicle(
            vehicle_uid=uid, plate_number=plate, plate_confidence=plate_conf or 0.0,
            vehicle_class=vehicle_class, color=color, first_seen=ts, last_seen=ts,
            appearance=appearance, observation_count=0,
        )
        self.db.add(v)
        self.db.flush()
        return uid

    def record_observation(self, *, vehicle_uid: str, camera_id: str, tracking_id: str | None,
                           plate: str | None, plate_conf: float, vehicle_class: str, color: str,
                           speed_kmh: float | None, det_conf: float, direction: str,
                           frame_path: str, appearance: dict, timestamp: dt.datetime,
                           assoc_conf: float) -> None:
        obs = VehicleObservation(
            vehicle_uid=vehicle_uid, camera_id=camera_id, tracking_id=tracking_id,
            plate_number=plate, vehicle_class=vehicle_class, color=color, speed_kmh=speed_kmh,
            detection_confidence=det_conf, plate_confidence=plate_conf, direction=direction,
            frame_path=frame_path, timestamp=timestamp,
        )
        self.db.add(obs)

        v = self.db.scalar(select(Vehicle).where(Vehicle.vehicle_uid == vehicle_uid))
        if v:
            v.last_seen = timestamp
            v.observation_count = (v.observation_count or 0) + 1
            if plate and (not v.plate_number or plate_conf > (v.plate_confidence or 0)):
                v.plate_number = plate
                v.plate_confidence = plate_conf
            if color and color != "unknown" and v.color == "unknown":
                v.color = color
            if appearance and appearance.get("hist"):
                v.appearance = appearance

        self._update_journey(vehicle_uid, camera_id, timestamp, speed_kmh, assoc_conf, v.plate_number if v else plate)

    def _update_journey(self, vehicle_uid, camera_id, ts, speed_kmh, assoc_conf, plate) -> None:
        j = self.db.scalar(select(VehicleJourney).where(VehicleJourney.vehicle_uid == vehicle_uid))
        hop = {"camera_id": camera_id, "timestamp": ts.isoformat(),
               "speed_kmh": round(speed_kmh, 1) if speed_kmh else None}
        if j is None:
            j = VehicleJourney(
                vehicle_uid=vehicle_uid, plate_number=plate, first_camera=camera_id, last_camera=camera_id,
                first_seen=ts, last_seen=ts, hop_count=1, path=[hop], association_confidence=assoc_conf,
            )
            self.db.add(j)
            return
        path = list(j.path or [])
        # only add a hop when the camera changes (new leg of the journey)
        if not path or path[-1].get("camera_id") != camera_id:
            path.append(hop)
            j.hop_count = len(path)
            j.last_camera = camera_id
        j.path = path
        j.last_seen = ts
        if plate and not j.plate_number:
            j.plate_number = plate
        j.association_confidence = round(min(j.association_confidence or 1.0, assoc_conf), 3)
