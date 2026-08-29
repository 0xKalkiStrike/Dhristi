"""Selective analysis: vehicle search, journeys and analytics aggregation."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Camera, PlateRead, SpeedEvent, TrafficEvent, Vehicle, VehicleJourney, VehicleObservation,
)
from app.schemas import VehicleSearchQuery


def search_vehicles(db: Session, q: VehicleSearchQuery) -> list[dict]:
    stmt = select(VehicleObservation)
    plate_map: dict[str, str] = {}
    if q.plate:
        pat = f"%{q.plate.upper()}%"
        # Plates are maintained on the Vehicle identity; resolve matching vehicles
        # so observations recorded before the plate was read still surface.
        vrows = db.execute(
            select(Vehicle.vehicle_uid, Vehicle.plate_number).where(Vehicle.plate_number.ilike(pat))
        ).all()
        plate_map = {uid: pl for uid, pl in vrows}
        uids = list(plate_map.keys())
        if uids:
            stmt = stmt.where(
                (VehicleObservation.plate_number.ilike(pat)) | (VehicleObservation.vehicle_uid.in_(uids))
            )
        else:
            stmt = stmt.where(VehicleObservation.plate_number.ilike(pat))
    if q.vehicle_type:
        stmt = stmt.where(VehicleObservation.vehicle_class == q.vehicle_type)
    if q.color:
        stmt = stmt.where(VehicleObservation.color == q.color)
    if q.camera_id:
        stmt = stmt.where(VehicleObservation.camera_id == q.camera_id)
    if q.start_time:
        stmt = stmt.where(VehicleObservation.timestamp >= q.start_time)
    if q.end_time:
        stmt = stmt.where(VehicleObservation.timestamp <= q.end_time)
    if q.min_speed is not None:
        stmt = stmt.where(VehicleObservation.speed_kmh >= q.min_speed)
    if q.max_speed is not None:
        stmt = stmt.where(VehicleObservation.speed_kmh <= q.max_speed)
    if q.direction:
        stmt = stmt.where(VehicleObservation.direction == q.direction)
    if q.min_confidence is not None:
        stmt = stmt.where(VehicleObservation.detection_confidence >= q.min_confidence)

    stmt = stmt.order_by(VehicleObservation.timestamp.desc()).limit(q.limit)
    rows = db.scalars(stmt).all()

    # optional filter by event type -> restrict to vehicles that have such an event
    if q.event_type:
        ev_uids = set(db.scalars(select(TrafficEvent.vehicle_uid).where(
            TrafficEvent.event_type == q.event_type)).all())
        rows = [r for r in rows if r.vehicle_uid in ev_uids]
    return [_obs_to_result(db, r, plate_map) for r in rows]


def _obs_to_result(db: Session, obs: VehicleObservation, plate_map: dict[str, str] | None = None) -> dict:
    plate = obs.plate_number or (plate_map or {}).get(obs.vehicle_uid)
    return {
        "vehicle_uid": obs.vehicle_uid,
        "plate_number": plate,
        "vehicle_class": obs.vehicle_class,
        "color": obs.color,
        "camera_id": obs.camera_id,
        "speed_kmh": obs.speed_kmh,
        "detection_confidence": obs.detection_confidence,
        "plate_confidence": obs.plate_confidence,
        "direction": obs.direction,
        "frame_path": obs.frame_path,
        "timestamp": obs.timestamp,
    }


def vehicle_detail(db: Session, vehicle_uid: str) -> dict | None:
    v = db.scalar(select(Vehicle).where(Vehicle.vehicle_uid == vehicle_uid))
    if not v:
        return None
    observations = db.scalars(select(VehicleObservation).where(
        VehicleObservation.vehicle_uid == vehicle_uid).order_by(VehicleObservation.timestamp)).all()
    journey = db.scalar(select(VehicleJourney).where(VehicleJourney.vehicle_uid == vehicle_uid))
    speed_events = db.scalars(select(SpeedEvent).where(
        SpeedEvent.vehicle_uid == vehicle_uid).order_by(SpeedEvent.timestamp)).all()
    plates = db.scalars(select(PlateRead).where(
        PlateRead.vehicle_uid == vehicle_uid).order_by(PlateRead.timestamp)).all()
    return {"vehicle": v, "observations": observations, "journey": journey,
            "speed_events": speed_events, "plate_reads": plates}


def analytics_summary(db: Session, since: dt.datetime | None = None) -> dict:
    since = since or (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1))
    total_detections = db.scalar(select(func.count()).select_from(VehicleObservation)
                                 .where(VehicleObservation.timestamp >= since)) or 0
    speeds = db.scalars(select(SpeedEvent.speed_kmh).where(SpeedEvent.timestamp >= since)).all()
    violations = db.scalar(select(func.count()).select_from(SpeedEvent)
                           .where(SpeedEvent.is_violation.is_(True), SpeedEvent.timestamp >= since)) or 0
    plate_reads = db.scalar(select(func.count()).select_from(PlateRead)
                            .where(PlateRead.timestamp >= since)) or 0
    cameras_online = db.scalar(select(func.count()).select_from(Camera).where(Camera.status == "online")) or 0
    cameras_total = db.scalar(select(func.count()).select_from(Camera)) or 0

    avg_speed = round(sum(speeds) / len(speeds), 1) if speeds else 0.0
    max_speed = round(max(speeds), 1) if speeds else 0.0

    # violations by hour
    by_hour: dict[int, int] = {}
    for row in db.scalars(select(SpeedEvent).where(SpeedEvent.is_violation.is_(True),
                                                   SpeedEvent.timestamp >= since)).all():
        by_hour[row.timestamp.hour] = by_hour.get(row.timestamp.hour, 0) + 1

    # by camera
    by_cam_rows = db.execute(
        select(SpeedEvent.camera_id, func.count()).where(SpeedEvent.timestamp >= since)
        .group_by(SpeedEvent.camera_id)).all()
    by_camera = {cid: cnt for cid, cnt in by_cam_rows}

    # vehicle categories
    cat_rows = db.execute(
        select(VehicleObservation.vehicle_class, func.count()).where(VehicleObservation.timestamp >= since)
        .group_by(VehicleObservation.vehicle_class)).all()
    categories = {c: cnt for c, cnt in cat_rows}

    # speed distribution buckets
    buckets = {"0-20": 0, "20-40": 0, "40-60": 0, "60-80": 0, "80-100": 0, "100+": 0}
    for s in speeds:
        if s < 20: buckets["0-20"] += 1
        elif s < 40: buckets["20-40"] += 1
        elif s < 60: buckets["40-60"] += 1
        elif s < 80: buckets["60-80"] += 1
        elif s < 100: buckets["80-100"] += 1
        else: buckets["100+"] += 1

    return {
        "vehicles_detected": total_detections,
        "average_speed_kmh": avg_speed,
        "max_speed_kmh": max_speed,
        "overspeed_events": violations,
        "anpr_reads": plate_reads,
        "cameras_online": cameras_online,
        "cameras_total": cameras_total,
        "camera_uptime_pct": round(100.0 * cameras_online / cameras_total, 1) if cameras_total else 0.0,
        "violations_by_hour": by_hour,
        "violations_by_camera": by_camera,
        "vehicle_categories": categories,
        "speed_distribution": buckets,
        "speed_samples": len(speeds),
    }
