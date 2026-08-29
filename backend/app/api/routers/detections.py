"""Detections, tracks, plate reads, speed & traffic events, alerts, analytics."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models import (
    Alert, AuditLog, Detection, PlateRead, SpeedEvent, Track, TrafficEvent,
)
from app.schemas import (
    DetectionOut, PlateReadOut, SpeedEventOut, TrackOut, TrafficEventOut,
)
from app.services import search as search_service

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/detections", response_model=list[DetectionOut])
def list_detections(camera_id: str | None = None, limit: int = Query(100, le=1000),
                    db: Session = Depends(get_db)):
    stmt = select(Detection).order_by(Detection.timestamp.desc()).limit(limit)
    if camera_id:
        stmt = stmt.where(Detection.camera_id == camera_id)
    return db.scalars(stmt).all()


@router.get("/tracks", response_model=list[TrackOut])
def list_tracks(camera_id: str | None = None, limit: int = Query(100, le=1000),
                db: Session = Depends(get_db)):
    stmt = select(Track).order_by(Track.last_seen.desc()).limit(limit)
    if camera_id:
        stmt = stmt.where(Track.camera_id == camera_id)
    return db.scalars(stmt).all()


@router.get("/plate-reads", response_model=list[PlateReadOut])
def list_plate_reads(camera_id: str | None = None, needs_verification: bool | None = None,
                     limit: int = Query(100, le=1000), db: Session = Depends(get_db)):
    stmt = select(PlateRead).order_by(PlateRead.timestamp.desc()).limit(limit)
    if camera_id:
        stmt = stmt.where(PlateRead.camera_id == camera_id)
    if needs_verification is not None:
        stmt = stmt.where(PlateRead.needs_verification.is_(needs_verification))
    return db.scalars(stmt).all()


@router.get("/speed-events", response_model=list[SpeedEventOut])
def list_speed_events(camera_id: str | None = None, only_violations: bool = False,
                      limit: int = Query(100, le=1000), db: Session = Depends(get_db)):
    stmt = select(SpeedEvent).order_by(SpeedEvent.timestamp.desc()).limit(limit)
    if camera_id:
        stmt = stmt.where(SpeedEvent.camera_id == camera_id)
    if only_violations:
        stmt = stmt.where(SpeedEvent.is_violation.is_(True))
    return db.scalars(stmt).all()


@router.get("/speed-events/{event_id}", response_model=SpeedEventOut)
def get_speed_event(event_id: int, db: Session = Depends(get_db)):
    from app.core.exceptions import NotFoundError
    ev = db.get(SpeedEvent, event_id)
    if not ev:
        raise NotFoundError("speed event not found")
    return ev


@router.get("/traffic-events", response_model=list[TrafficEventOut])
def list_traffic_events(camera_id: str | None = None, event_type: str | None = None,
                        limit: int = Query(100, le=1000), db: Session = Depends(get_db)):
    stmt = select(TrafficEvent).order_by(TrafficEvent.timestamp.desc()).limit(limit)
    if camera_id:
        stmt = stmt.where(TrafficEvent.camera_id == camera_id)
    if event_type:
        stmt = stmt.where(TrafficEvent.event_type == event_type)
    return db.scalars(stmt).all()


@router.get("/alerts")
def list_alerts(limit: int = Query(50, le=500), db: Session = Depends(get_db)):
    rows = db.scalars(select(Alert).order_by(Alert.timestamp.desc()).limit(limit)).all()
    return [{"id": a.id, "alert_type": a.alert_type, "camera_id": a.camera_id, "message": a.message,
             "severity": a.severity, "acknowledged": a.acknowledged, "timestamp": a.timestamp}
            for a in rows]


@router.get("/audit-logs")
def list_audit_logs(limit: int = Query(100, le=500), db: Session = Depends(get_db)):
    rows = db.scalars(select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)).all()
    return [{"id": r.id, "actor": r.actor, "action": r.action, "entity": r.entity,
             "entity_id": r.entity_id, "detail": r.detail, "timestamp": r.timestamp} for r in rows]


@router.get("/analytics/summary")
def analytics_summary(hours: int = Query(24, ge=1, le=720), db: Session = Depends(get_db)):
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)
    return search_service.analytics_summary(db, since)
