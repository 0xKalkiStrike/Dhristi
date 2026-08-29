"""Pydantic v2 schemas (API request/response DTOs)."""
from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Cameras ----------
class CameraCreate(BaseModel):
    camera_id: Optional[str] = None
    name: str
    location: str = ""
    zone: str = ""
    orientation: str = ""
    source_type: str = "file"          # file|rtsp|webcam
    source_uri: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    enabled: bool = True


class CameraUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    zone: Optional[str] = None
    orientation: Optional[str] = None
    source_type: Optional[str] = None
    source_uri: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    enabled: Optional[bool] = None


class CameraOut(ORMBase):
    id: int
    camera_id: str
    name: str
    location: str
    zone: str
    orientation: str
    source_type: str
    # source_uri intentionally masked in read model (may hold rtsp creds)
    has_source: bool = False
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    enabled: bool
    status: str
    fps: float
    last_environment: str
    ai_status: str
    has_calibration: bool = False


# ---------- Calibration ----------
class CalibrationIn(BaseModel):
    method: str = "dual_line"
    line_a: list = Field(default_factory=list)
    line_b: list = Field(default_factory=list)
    real_distance_m: float = 0.0
    image_points: list = Field(default_factory=list)
    world_points: list = Field(default_factory=list)
    measurement_area: list = Field(default_factory=list)
    direction: str = ""
    speed_limit_kmh: float = 60.0
    frame_width: int = 0
    frame_height: int = 0


class CalibrationOut(ORMBase):
    id: int
    camera_pk: int
    method: str
    line_a: list
    line_b: list
    real_distance_m: float
    image_points: list
    world_points: list
    measurement_area: list
    direction: str
    speed_limit_kmh: float
    frame_width: int
    frame_height: int
    is_active: bool


# ---------- Detections / tracks ----------
class DetectionOut(ORMBase):
    id: int
    detection_id: str
    camera_id: str
    frame_id: int
    timestamp: dt.datetime
    vehicle_class: str
    confidence: float
    bbox: list
    center: list
    tracking_id: Optional[str] = None


class TrackOut(ORMBase):
    id: int
    tracking_id: str
    camera_id: str
    vehicle_class: str
    confidence: float
    first_frame: int
    last_frame: int
    first_seen: dt.datetime
    last_seen: dt.datetime
    vehicle_uid: Optional[str] = None


# ---------- Plates / speed / events ----------
class PlateReadOut(ORMBase):
    id: int
    camera_id: str
    tracking_id: Optional[str]
    vehicle_uid: Optional[str]
    raw_text: str
    normalized_text: str
    confidence: float
    ocr_engine: str
    valid_format: bool
    needs_verification: bool
    plate_bbox: list
    crop_path: str
    timestamp: dt.datetime


class SpeedEventOut(ORMBase):
    id: int
    camera_id: str
    tracking_id: Optional[str]
    vehicle_uid: Optional[str]
    plate_number: Optional[str]
    distance_m: float
    elapsed_s: float
    speed_kmh: float
    speed_limit_kmh: float
    excess_kmh: float
    method: str
    confidence: float
    is_violation: bool
    timestamp: dt.datetime
    details: dict


class TrafficEventOut(ORMBase):
    id: int
    event_type: str
    camera_id: str
    tracking_id: Optional[str]
    vehicle_uid: Optional[str]
    plate_number: Optional[str]
    severity: str
    confidence: float
    reason: str
    details: dict
    timestamp: dt.datetime


# ---------- Vehicles / journey ----------
class VehicleOut(ORMBase):
    id: int
    vehicle_uid: str
    plate_number: Optional[str]
    vehicle_class: str
    color: str
    plate_confidence: float
    first_seen: dt.datetime
    last_seen: dt.datetime
    observation_count: int


class ObservationOut(ORMBase):
    id: int
    vehicle_uid: str
    camera_id: str
    tracking_id: Optional[str]
    plate_number: Optional[str]
    vehicle_class: str
    color: str
    speed_kmh: Optional[float]
    detection_confidence: float
    plate_confidence: float
    direction: str
    frame_path: str
    timestamp: dt.datetime


class JourneyOut(ORMBase):
    id: int
    vehicle_uid: str
    plate_number: Optional[str]
    first_camera: str
    last_camera: str
    first_seen: dt.datetime
    last_seen: dt.datetime
    hop_count: int
    path: list
    association_confidence: float


class VehicleDetail(BaseModel):
    vehicle: VehicleOut
    observations: list[ObservationOut]
    journey: Optional[JourneyOut] = None
    speed_events: list[SpeedEventOut]
    plate_reads: list[PlateReadOut]


# ---------- Search ----------
class VehicleSearchQuery(BaseModel):
    plate: Optional[str] = None
    vehicle_type: Optional[str] = None
    color: Optional[str] = None
    camera_id: Optional[str] = None
    start_time: Optional[dt.datetime] = None
    end_time: Optional[dt.datetime] = None
    min_speed: Optional[float] = None
    max_speed: Optional[float] = None
    event_type: Optional[str] = None
    min_confidence: Optional[float] = None
    direction: Optional[str] = None
    limit: int = 100


# ---------- System / analysis ----------
class HealthOut(BaseModel):
    status: str
    version: str
    ai_runtime: str
    detector_backend: str
    ocr_engine: str
    device: str
    database: str
    mongo_enabled: bool = False
    mongo_connected: bool = False
    cuda_available: bool
    active_pipelines: int
    uptime_seconds: float


class AnalysisStart(BaseModel):
    camera_id: str
    loop: bool = False


class MessageOut(BaseModel):
    message: str
    data: Optional[Any] = None
