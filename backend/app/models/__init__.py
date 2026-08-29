"""SQLAlchemy ORM models for DRISHTI-V."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160), default="")
    role: Mapped[str] = mapped_column(String(40), default="operator")  # admin|operator|viewer
    password_hash: Mapped[str] = mapped_column(String(256), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)


class Camera(Base):
    __tablename__ = "cameras"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)  # e.g. CAM-001
    name: Mapped[str] = mapped_column(String(160))
    location: Mapped[str] = mapped_column(String(200), default="")
    zone: Mapped[str] = mapped_column(String(80), default="", index=True)
    orientation: Mapped[str] = mapped_column(String(40), default="")
    source_type: Mapped[str] = mapped_column(String(20), default="file")  # file|rtsp|webcam
    source_uri: Mapped[str] = mapped_column(String(500), default="")       # path or rtsp url (never logged raw)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default="offline")     # online|offline|error
    fps: Mapped[float] = mapped_column(Float, default=0.0)
    last_environment: Mapped[str] = mapped_column(String(40), default="unknown")
    ai_status: Mapped[str] = mapped_column(String(40), default="idle")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)

    calibration = relationship("CameraCalibration", back_populates="camera", uselist=False,
                               cascade="all, delete-orphan")


class CameraCalibration(Base):
    __tablename__ = "camera_calibrations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_pk: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    method: Mapped[str] = mapped_column(String(30), default="dual_line")  # dual_line|homography
    # dual-line params (image coords) & real distance between lines (metres)
    line_a: Mapped[list] = mapped_column(JSON, default=list)   # [[x1,y1],[x2,y2]]
    line_b: Mapped[list] = mapped_column(JSON, default=list)
    real_distance_m: Mapped[float] = mapped_column(Float, default=0.0)
    # homography params: 4 image points + 4 world points (metres)
    image_points: Mapped[list] = mapped_column(JSON, default=list)
    world_points: Mapped[list] = mapped_column(JSON, default=list)
    measurement_area: Mapped[list] = mapped_column(JSON, default=list)  # polygon
    direction: Mapped[str] = mapped_column(String(40), default="")
    speed_limit_kmh: Mapped[float] = mapped_column(Float, default=60.0)
    frame_width: Mapped[int] = mapped_column(Integer, default=0)
    frame_height: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)

    camera = relationship("Camera", back_populates="calibration")


class Vehicle(Base):
    __tablename__ = "vehicles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_uid: Mapped[str] = mapped_column(String(40), unique=True, index=True)  # VH-982731
    plate_number: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    vehicle_class: Mapped[str] = mapped_column(String(30), default="unknown")
    color: Mapped[str] = mapped_column(String(30), default="unknown")
    plate_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    first_seen: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    last_seen: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    appearance: Mapped[dict] = mapped_column(JSON, default=dict)  # reid embedding / color hist
    observation_count: Mapped[int] = mapped_column(Integer, default=0)


class Detection(Base):
    __tablename__ = "detections"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    detection_id: Mapped[str] = mapped_column(String(48), index=True)
    camera_id: Mapped[str] = mapped_column(String(40), index=True)
    frame_id: Mapped[int] = mapped_column(Integer, default=0)
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    vehicle_class: Mapped[str] = mapped_column(String(30))
    confidence: Mapped[float] = mapped_column(Float)
    bbox: Mapped[list] = mapped_column(JSON)      # [x1,y1,x2,y2]
    center: Mapped[list] = mapped_column(JSON)    # [cx,cy]
    tracking_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)


class Track(Base):
    __tablename__ = "tracks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tracking_id: Mapped[str] = mapped_column(String(40), index=True)  # TRACK-000127
    camera_id: Mapped[str] = mapped_column(String(40), index=True)
    vehicle_class: Mapped[str] = mapped_column(String(30), default="unknown")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    first_frame: Mapped[int] = mapped_column(Integer, default=0)
    last_frame: Mapped[int] = mapped_column(Integer, default=0)
    first_seen: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    last_seen: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)
    vehicle_uid: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)


class TrackPoint(Base):
    __tablename__ = "track_points"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tracking_id: Mapped[str] = mapped_column(String(40), index=True)
    camera_id: Mapped[str] = mapped_column(String(40), index=True)
    frame_id: Mapped[int] = mapped_column(Integer)
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)
    bbox: Mapped[list] = mapped_column(JSON)
    center: Mapped[list] = mapped_column(JSON)


class PlateRead(Base):
    __tablename__ = "plate_reads"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[str] = mapped_column(String(40), index=True)
    tracking_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    vehicle_uid: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    raw_text: Mapped[str] = mapped_column(String(40), default="")
    normalized_text: Mapped[str] = mapped_column(String(20), default="", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    ocr_engine: Mapped[str] = mapped_column(String(20), default="")
    valid_format: Mapped[bool] = mapped_column(Boolean, default=False)
    needs_verification: Mapped[bool] = mapped_column(Boolean, default=True)
    plate_bbox: Mapped[list] = mapped_column(JSON, default=list)
    crop_path: Mapped[str] = mapped_column(String(300), default="")
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class SpeedEvent(Base):
    __tablename__ = "speed_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[str] = mapped_column(String(40), index=True)
    tracking_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    vehicle_uid: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    plate_number: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    distance_m: Mapped[float] = mapped_column(Float)
    elapsed_s: Mapped[float] = mapped_column(Float)
    speed_kmh: Mapped[float] = mapped_column(Float, index=True)
    speed_limit_kmh: Mapped[float] = mapped_column(Float)
    excess_kmh: Mapped[float] = mapped_column(Float, default=0.0)
    method: Mapped[str] = mapped_column(String(40))
    confidence: Mapped[float] = mapped_column(Float)
    calibration_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_violation: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)  # explainability payload


class TrafficEvent(Base):
    __tablename__ = "traffic_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)  # overspeed|wrong_way|stopped|...
    camera_id: Mapped[str] = mapped_column(String(40), index=True)
    tracking_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    vehicle_uid: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    plate_number: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    severity: Mapped[str] = mapped_column(String(20), default="info")  # info|warning|critical
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class VehicleObservation(Base):
    __tablename__ = "vehicle_observations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_uid: Mapped[str] = mapped_column(String(40), index=True)
    camera_id: Mapped[str] = mapped_column(String(40), index=True)
    tracking_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    plate_number: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    vehicle_class: Mapped[str] = mapped_column(String(30), default="unknown")
    color: Mapped[str] = mapped_column(String(30), default="unknown")
    speed_kmh: Mapped[float | None] = mapped_column(Float, nullable=True)
    detection_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    plate_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    direction: Mapped[str] = mapped_column(String(30), default="")
    frame_path: Mapped[str] = mapped_column(String(300), default="")
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class VehicleJourney(Base):
    __tablename__ = "vehicle_journeys"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_uid: Mapped[str] = mapped_column(String(40), index=True)
    plate_number: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    first_camera: Mapped[str] = mapped_column(String(40), default="")
    last_camera: Mapped[str] = mapped_column(String(40), default="")
    first_seen: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    last_seen: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)
    hop_count: Mapped[int] = mapped_column(Integer, default=0)
    path: Mapped[list] = mapped_column(JSON, default=list)  # ordered camera hops w/ metadata
    association_confidence: Mapped[float] = mapped_column(Float, default=0.0)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_type: Mapped[str] = mapped_column(String(40), index=True)
    camera_id: Mapped[str] = mapped_column(String(40), index=True)
    message: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), default="info")
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    reference_id: Mapped[str | None] = mapped_column(String(48), nullable=True)
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(80), default="system")
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity: Mapped[str] = mapped_column(String(80), default="")
    entity_id: Mapped[str] = mapped_column(String(80), default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow, index=True)


# Composite indexes for common query patterns
Index("ix_detections_cam_ts", Detection.camera_id, Detection.timestamp)
Index("ix_speed_cam_ts", SpeedEvent.camera_id, SpeedEvent.timestamp)
Index("ix_events_type_ts", TrafficEvent.event_type, TrafficEvent.timestamp)
Index("ix_obs_vehicle_ts", VehicleObservation.vehicle_uid, VehicleObservation.timestamp)
