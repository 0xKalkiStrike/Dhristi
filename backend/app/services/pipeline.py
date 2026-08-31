"""Per-camera processing pipeline & manager.

Orchestrates: video -> environment analysis -> adaptive enhancement -> detection
-> tracking -> speed -> ANPR -> identity -> events -> DB -> WebSocket.

Each camera runs in its own worker thread with its own DB session so one failing
camera never stops the platform. Frame sampling keeps CPU load reasonable.
"""
from __future__ import annotations

import datetime as dt
import threading
import time
import uuid
from typing import Optional

import cv2

from app.ai.anpr.pipeline import ANPRPipeline
from app.ai.detection.base import Detection
from app.ai.detection.factory import build_detector, resolve_device
from app.ai.enhancement.pipeline import build_enhancer
from app.ai.environment.classifier import ImageQualityService
from app.ai.reidentification import reid
from app.ai.speed.calibration import Calibration
from app.ai.speed.estimator import SpeedEstimator
from app.ai.tracking.byte_tracker import ByteTracker
from app.core.config import settings
from app.core.logging_config import get_logger
from app.events.detectors import EventEngine
from app.models import (
    Alert, Camera, Detection as DetectionModel, PlateRead, SpeedEvent, Track,
    TrackPoint, TrafficEvent,
)
from app.services.identity import VehicleIdentityService
from app.database.session import SessionLocal
from app.utils.draw import draw_overlays, encode_jpeg
from app.websocket.manager import manager

logger = get_logger("drishti.pipeline")

# Shared, lazily-initialised heavy models (thread-safe enough for inference use).
_shared_lock = threading.Lock()
_shared_detector = None
_shared_anpr = None


def get_shared_detector():
    global _shared_detector
    with _shared_lock:
        if _shared_detector is None:
            _shared_detector = build_detector()
            try:
                _shared_detector.warmup()
            except Exception:
                pass
    return _shared_detector


def get_shared_anpr():
    global _shared_anpr
    with _shared_lock:
        if _shared_anpr is None:
            _shared_anpr = ANPRPipeline()
    return _shared_anpr


class CameraPipeline:
    def __init__(self, camera: Camera, loop: bool = False, demo_detector: Optional[str] = None):
        self.camera_pk = camera.id
        self.camera_id = camera.camera_id
        self.camera_name = camera.name
        self.source_type = camera.source_type
        self.source_uri = camera.source_uri
        self.loop = loop
        self.demo_detector = demo_detector

        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._frame_cond = threading.Condition()
        self._frame_seq = 0
        self.running = False
        self.error: Optional[str] = None
        self.latest_jpeg: bytes = b""
        self.stats = {"frames": 0, "detections": 0, "fps": 0.0, "tracks": 0,
                      "plates": 0, "speed_events": 0, "traffic_events": 0,
                      "environment": "unknown", "backend": "", "inference_ms": 0.0}

        # per-track bookkeeping
        self._track_vehicle: dict[str, str] = {}
        self._track_obs_speed: set[str] = set()
        self._plate_attempts: dict[str, int] = {}
        self._plate_done: set[str] = set()
        self._persisted_tracks: set[str] = set()

    # ---------- lifecycle ----------
    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name=f"pipe-{self.camera_id}", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self.running = False
        with self._frame_cond:
            self._frame_cond.notify_all()

    def is_alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def get_latest_frame(self, last_seq: int, timeout: float = 0.5) -> tuple[int, bytes]:
        """Wait for and retrieve a newer frame than last_seq, or return current."""
        with self._frame_cond:
            if self._frame_seq == last_seq and self.running:
                self._frame_cond.wait(timeout)
            return self._frame_seq, self.latest_jpeg

    # ---------- main loop ----------
    def _run(self) -> None:
        from app.video.sources import build_video_source
        db = SessionLocal()
        self.running = True
        try:
            detector = (build_detector(self.demo_detector) if self.demo_detector else get_shared_detector())
            self.stats["backend"] = detector.name
            tracker = ByteTracker(settings.track_high_thresh, settings.track_low_thresh,
                                  settings.track_max_age, settings.track_min_hits, settings.track_iou_match)
            quality = ImageQualityService()
            enhancer = build_enhancer()

            camera = db.get(Camera, self.camera_pk)
            cal_orm = camera.calibration if camera else None
            calibration = Calibration.from_orm(cal_orm) if cal_orm else None
            estimator = SpeedEstimator(calibration, settings.speed_min_confidence)
            events = EventEngine(
                allowed_direction=(cal_orm.direction or None) if cal_orm else None,
                restricted_zone=(cal_orm.measurement_area or None) if (cal_orm and cal_orm.method == "zone") else None,
            )
            identity = VehicleIdentityService(db)

            source = build_video_source(self.source_type, self.source_uri)
            source.open()
            self._set_status(db, "online")
            manager.broadcast_threadsafe({"type": "camera_status",
                                          "camera_id": self.camera_id, "status": "online"})

            src_fps = source.fps or 25.0
            # For live sources, sync exactly to their hardware rate to eliminate pacing stutter
            target_fps = src_fps if getattr(source, "is_live", False) else max(1.0, float(settings.process_fps))
            step = max(1, int(round(src_fps / target_fps))) if src_fps > target_fps * 1.3 else 1
            det_interval = settings.detect_every_n_frames
            raw_index = 0
            processed = 0
            env_report = None
            last_ping = time.time()
            t_fps = time.time()

            while not self._stop.is_set():
                fd = source.read()
                if not fd.ok:
                    if self.loop and source.frame_count > 0:
                        source.seek(0)
                        tracker.reset()
                        estimator = SpeedEstimator(calibration, settings.speed_min_confidence)
                        self._track_obs_speed.clear()
                        continue
                    if getattr(source, "is_live", False):
                        time.sleep(0.01)  # live source idle — wait briefly
                        continue
                    break
                raw_index += 1
                if step > 1 and raw_index % step != 0:
                    continue
                processed += 1
                frame = fd.frame
                t0 = time.time()

                # environment analysis (periodic) + adaptive enhancement
                if env_report is None or processed % 30 == 0:
                    env_report = quality.analyze(frame)
                    self.stats["environment"] = env_report.environment
                proc_frame = frame
                enh = enhancer.enhance(frame, env_report)
                used_backend_note = ""
                detections: list[Detection] | None = None

                # Cheap classical detector runs every frame for smooth tracking;
                # expensive deep models run on the sampled interval.
                run_detect = (not detector.is_deep_model) or (processed % det_interval == 1) or (processed == 1)
                if run_detect:
                    input_frame = enh.frame if (enh.changed and env_report and env_report.environment in ("fog", "low_light", "night")) else frame
                    detections = detector.detect(input_frame, self.camera_id, fd.frame_id)
                    if enh.changed:
                        used_backend_note = "enhanced"
                self.stats["inference_ms"] = round((time.time() - t0) * 1000, 1)

                # tracking (time_s = source-relative time for accurate speed timing)
                tracks = tracker.update(detections, fd.frame_id, time_s=_epoch(fd.timestamp), is_detect_frame=run_detect)
                self.stats["tracks"] = len(tracks)
                if run_detect and detections is not None:
                    self.stats["detections"] += len(detections)

                # persist detections (sampled) + track points
                if run_detect and detections:
                    self._persist_detections(db, detections, fd.frame_id)
                    manager.broadcast_threadsafe({
                        "type": "vehicle_detected", "camera_id": self.camera_id,
                        "count": len(detections), "frame_id": fd.frame_id,
                        "classes": _class_counts(detections)})

                active_count = len(tracks)
                for t in tracks:
                    if t.age == 0:
                        self._persist_track_point(db, t, fd.frame_id)
                        self._maybe_persist_track(db, t)

                    # speed (streaming)
                    if estimator.available:
                        m = estimator.update(t.track_id, t.center, _epoch(fd.timestamp))
                        if m and m.confidence >= settings.speed_min_confidence:
                            t._speed_label = f"{m.speed_kmh:.0f}km/h"  # type: ignore[attr-defined]
                            self._handle_speed(db, t, m)

                    # identity on confirmation (only on actively detected frames)
                    if t.confirmed and t.age == 0 and t.track_id not in self._track_vehicle:
                        self._handle_identity(db, identity, t, frame, fd)

                    # ANPR gating (only on actively detected frames)
                    if t.confirmed and t.age == 0 and t.track_id not in self._plate_done:
                        self._maybe_anpr(db, identity, t, frame, fd)

                    # events
                    for evt in filter(None, [events.check_wrong_way(t), events.check_stopped(t),
                                             events.check_dwell(t, fd.frame_id),
                                             events.check_restricted_zone(t)]):
                        self._handle_event(db, evt)

                cong = events.check_congestion(self.camera_id, active_count, fd.frame_id)
                if cong:
                    self._handle_event(db, cong)

                # annotated preview (clean original frame)
                annotated = draw_overlays(frame, tracks, calibration,
                                          self.stats["environment"], detector.name + (f"/{used_backend_note}" if used_backend_note else ""),
                                          self.camera_name)
                self.latest_jpeg = encode_jpeg(annotated)
                with self._frame_cond:
                    self._frame_seq += 1
                    self._frame_cond.notify_all()

                # fps + periodic commit/status
                self.stats["frames"] = processed
                if processed % 15 == 0:
                    now = time.time()
                    self.stats["fps"] = round(15.0 / max(1e-6, now - t_fps), 1)
                    t_fps = now
                    db.commit()
                    camera = db.get(Camera, self.camera_pk)
                    if camera:
                        camera.fps = self.stats["fps"]
                        camera.last_environment = self.stats["environment"]
                        camera.ai_status = f"processing:{detector.name}"
                        db.commit()
                if time.time() - last_ping > 2:
                    manager.broadcast_threadsafe({"type": "camera_status", "camera_id": self.camera_id,
                                                  "status": "online", "fps": self.stats["fps"],
                                                  "environment": self.stats["environment"],
                                                  "tracks": active_count})
                    last_ping = time.time()

                # Pace only file sources — live sources (RTSP/webcam) are
                # already gated by the background reader thread's own cadence;
                # sleeping here adds a second layer of lag on top of it.
                if not getattr(source, "is_live", False):
                    elapsed = time.time() - t0
                    target_dt = 1.0 / target_fps
                    if elapsed < target_dt:
                        time.sleep(target_dt - elapsed)

            source.release()
            db.commit()
            self._set_status(db, "offline")
            manager.broadcast_threadsafe({"type": "camera_status", "camera_id": self.camera_id, "status": "offline"})
            with self._frame_cond:
                self._frame_cond.notify_all()
            logger.info("pipeline finished", extra={"extra_fields": {"camera": self.camera_id, "frames": processed}})
        except Exception as exc:  # graceful degradation
            self.error = str(exc)
            logger.error("pipeline error on %s: %s", self.camera_id, exc, exc_info=True)
            try:
                self._set_status(db, "error")
                manager.broadcast_threadsafe({"type": "camera_status", "camera_id": self.camera_id,
                                              "status": "error", "detail": str(exc)})
            except Exception:
                pass
            with self._frame_cond:
                self._frame_cond.notify_all()
        finally:
            self.running = False
            with self._frame_cond:
                self._frame_cond.notify_all()
            try:
                db.close()
            except Exception:
                pass


    # ---------- persistence helpers ----------
    def _set_status(self, db, status: str) -> None:
        cam = db.get(Camera, self.camera_pk)
        if cam:
            cam.status = status
            if status != "online":
                cam.ai_status = "idle"
                cam.fps = 0.0
            db.commit()

    def _persist_detections(self, db, detections, frame_id) -> None:
        now = dt.datetime.now(dt.timezone.utc)
        for d in detections:
            db.add(DetectionModel(
                detection_id=uuid.uuid4().hex[:16], camera_id=self.camera_id, frame_id=frame_id,
                timestamp=now, vehicle_class=d.vehicle_class, confidence=d.confidence,
                bbox=[round(v, 1) for v in d.bbox], center=[round(v, 1) for v in d.center],
                tracking_id=d.tracking_id))

    def _persist_track_point(self, db, t, frame_id) -> None:
        if frame_id % 3 != 0:
            return
        db.add(TrackPoint(tracking_id=t.track_id, camera_id=self.camera_id, frame_id=frame_id,
                          timestamp=dt.datetime.now(dt.timezone.utc),
                          bbox=[round(v, 1) for v in t.bbox], center=[round(v, 1) for v in t.center]))

    def _maybe_persist_track(self, db, t) -> None:
        now = dt.datetime.now(dt.timezone.utc)
        existing = db.query(Track).filter(Track.tracking_id == t.track_id,
                                          Track.camera_id == self.camera_id).first()
        if existing:
            existing.last_frame = t.last_frame
            existing.last_seen = now
            existing.confidence = t.confidence
            existing.vehicle_class = t.vehicle_class
            existing.vehicle_uid = self._track_vehicle.get(t.track_id)
        else:
            db.add(Track(tracking_id=t.track_id, camera_id=self.camera_id, vehicle_class=t.vehicle_class,
                         confidence=t.confidence, first_frame=t.first_frame, last_frame=t.last_frame,
                         first_seen=t.first_seen, last_seen=now,
                         vehicle_uid=self._track_vehicle.get(t.track_id)))

    def _crop(self, frame, bbox):
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = (int(v) for v in bbox)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 <= x1 or y2 <= y1:
            return None
        return frame[y1:y2, x1:x2]

    def _handle_identity(self, db, identity, t, frame, fd) -> None:
        crop = self._crop(frame, t.bbox)
        appearance = reid.appearance_signature(crop) if crop is not None else {"hist": [], "color": "unknown"}
        color = appearance.get("color", "unknown")
        ts = dt.datetime.now(dt.timezone.utc)
        uid, assoc = identity.resolve(camera_id=self.camera_id, plate=None, plate_conf=0.0,
                                      appearance=appearance, vehicle_class=t.vehicle_class,
                                      color=color, timestamp=ts)
        self._track_vehicle[t.track_id] = uid
        identity.record_observation(vehicle_uid=uid, camera_id=self.camera_id, tracking_id=t.track_id,
                                    plate=None, plate_conf=0.0, vehicle_class=t.vehicle_class, color=color,
                                    speed_kmh=None, det_conf=t.confidence, direction="",
                                    frame_path="", appearance=appearance, timestamp=ts, assoc_conf=assoc)
        db.flush()
        manager.broadcast_threadsafe({"type": "vehicle_updated", "camera_id": self.camera_id,
                                      "vehicle_uid": uid, "vehicle_class": t.vehicle_class,
                                      "color": color, "tracking_id": t.track_id,
                                      "association_confidence": assoc})

    def _run_anpr_bg(self, identity, camera_id, track_id, uid, crop) -> None:
        from app.database.session import SessionLocal
        from app.models import PlateRead, Vehicle, VehicleObservation
        
        anpr = get_shared_anpr()
        result = anpr.read_plate(crop, save=True, camera_id=camera_id, tracking_id=track_id)
        if result is None or not result.normalized_text:
            return
            
        try:
            with SessionLocal() as db:
                db.add(PlateRead(camera_id=camera_id, tracking_id=track_id, vehicle_uid=uid,
                                 raw_text=result.raw_text, normalized_text=result.normalized_text,
                                 confidence=result.confidence, ocr_engine=result.ocr_engine,
                                 valid_format=result.valid_format, needs_verification=result.needs_verification,
                                 plate_bbox=list(result.plate_bbox), crop_path=result.crop_path,
                                 timestamp=dt.datetime.now(dt.timezone.utc)))
                self.stats["plates"] += 1
                if result.valid_format and not result.needs_verification:
                    self._plate_done.add(track_id)
                if uid:
                    v = db.query(Vehicle).filter_by(vehicle_uid=uid).first()
                    if v and (not v.plate_number or result.confidence > (v.plate_confidence or 0)):
                        v.plate_number = result.normalized_text
                        v.plate_confidence = result.confidence
                    db.query(VehicleObservation).filter(
                        VehicleObservation.vehicle_uid == uid,
                        VehicleObservation.plate_number.is_(None),
                    ).update({VehicleObservation.plate_number: result.normalized_text}, synchronize_session=False)
                db.commit()
                
            manager.broadcast_threadsafe({"type": "plate_detected", "camera_id": camera_id,
                                          "vehicle_uid": uid, "tracking_id": track_id,
                                          "plate": result.normalized_text, "confidence": result.confidence,
                                          "needs_verification": result.needs_verification,
                                          "valid_format": result.valid_format})
        except Exception as exc:
            logger.error("anpr bg thread error: %s", exc)

    def _maybe_anpr(self, db, identity, t, frame, fd) -> None:
        attempts = self._plate_attempts.get(t.track_id, 0)
        if attempts >= 10:
            return
        # gate: require a reasonably sized vehicle box
        if t.height < 40 or t.width < 40:
            return
        self._plate_attempts[t.track_id] = attempts + 1
        crop = self._crop(frame, t.bbox)
        if crop is None:
            return
        
        uid = self._track_vehicle.get(t.track_id)
        threading.Thread(
            target=self._run_anpr_bg,
            args=(identity, self.camera_id, t.track_id, uid, crop.copy()),
            daemon=True
        ).start()

    def _handle_speed(self, db, t, m) -> None:
        if t.track_id in self._track_obs_speed:
            return
        self._track_obs_speed.add(t.track_id)
        uid = self._track_vehicle.get(t.track_id)
        plate = self._plate_for(db, uid)
        se = SpeedEvent(camera_id=self.camera_id, tracking_id=t.track_id, vehicle_uid=uid, plate_number=plate,
                        distance_m=m.distance_m, elapsed_s=m.elapsed_s, speed_kmh=m.speed_kmh,
                        speed_limit_kmh=m.speed_limit_kmh, excess_kmh=m.excess_kmh, method=m.method,
                        confidence=m.confidence, calibration_id=m.calibration_id, is_violation=m.is_violation,
                        details=m.to_dict(), timestamp=dt.datetime.now(dt.timezone.utc))
        db.add(se)
        self.stats["speed_events"] += 1
        db.flush()
        manager.broadcast_threadsafe({"type": "speed_event", "camera_id": self.camera_id,
                                      "vehicle_uid": uid, "plate": plate, "tracking_id": t.track_id,
                                      "speed_kmh": round(m.speed_kmh, 1), "limit": m.speed_limit_kmh,
                                      "is_violation": m.is_violation, "confidence": m.confidence,
                                      "method": m.method})
        if m.is_violation:
            evt = EventEngine().check_overspeed(t, m)
            if evt:
                self._handle_event(db, evt)

    def _handle_event(self, db, evt) -> None:
        uid = self._track_vehicle.get(evt.tracking_id) if evt.tracking_id else None
        plate = self._plate_for(db, uid)
        te = TrafficEvent(event_type=evt.event_type, camera_id=self.camera_id, tracking_id=evt.tracking_id,
                          vehicle_uid=uid, plate_number=plate, severity=evt.severity, confidence=evt.confidence,
                          reason=evt.reason, details=evt.details, timestamp=dt.datetime.now(dt.timezone.utc))
        db.add(te)
        db.add(Alert(alert_type=evt.event_type, camera_id=self.camera_id, message=evt.reason,
                     severity=evt.severity, reference_id=evt.tracking_id))
        self.stats["traffic_events"] += 1
        db.flush()
        manager.broadcast_threadsafe({"type": "traffic_event", "camera_id": self.camera_id,
                                      "event_type": evt.event_type, "severity": evt.severity,
                                      "vehicle_uid": uid, "plate": plate, "tracking_id": evt.tracking_id,
                                      "reason": evt.reason, "confidence": evt.confidence,
                                      "details": evt.details})

    def _plate_for(self, db, uid) -> Optional[str]:
        if not uid:
            return None
        from app.models import Vehicle
        v = db.query(Vehicle).filter_by(vehicle_uid=uid).first()
        return v.plate_number if v else None


def _epoch(ts: float) -> float:
    return float(ts)


def _mean_conf(dets) -> float:
    return sum(d.confidence for d in dets) / len(dets) if dets else 0.0


def _class_counts(dets) -> dict:
    out: dict[str, int] = {}
    for d in dets:
        out[d.vehicle_class] = out.get(d.vehicle_class, 0) + 1
    return out


class PipelineManager:
    def __init__(self):
        self._pipelines: dict[str, CameraPipeline] = {}
        self._lock = threading.Lock()

    def start(self, camera: Camera, loop: bool = False, demo_detector: Optional[str] = None) -> CameraPipeline:
        with self._lock:
            existing = self._pipelines.get(camera.camera_id)
            if existing and existing.is_alive():
                return existing
            p = CameraPipeline(camera, loop=loop, demo_detector=demo_detector)
            self._pipelines[camera.camera_id] = p
        p.start()
        return p

    def stop(self, camera_id: str) -> bool:
        with self._lock:
            p = self._pipelines.get(camera_id)
        if p:
            p.stop()
            return True
        return False

    def stop_all(self) -> None:
        for p in list(self._pipelines.values()):
            p.stop()

    def get(self, camera_id: str) -> Optional[CameraPipeline]:
        return self._pipelines.get(camera_id)

    def status(self, camera_id: str) -> Optional[dict]:
        p = self._pipelines.get(camera_id)
        if not p:
            return None
        return {"camera_id": camera_id, "running": p.is_alive(), "error": p.error, **p.stats}

    @property
    def active_count(self) -> int:
        return sum(1 for p in self._pipelines.values() if p.is_alive())

    def all_status(self) -> list[dict]:
        return [self.status(cid) for cid in self._pipelines]


pipeline_manager = PipelineManager()
