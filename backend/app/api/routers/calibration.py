"""Speed calibration endpoints (configure, preview, test)."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.speed.calibration import Calibration
from app.ai.speed.estimator import SpeedEstimator
from app.core.exceptions import CalibrationError, NotFoundError
from app.database.session import get_db
from app.models import AuditLog, Camera, CameraCalibration
from app.schemas import CalibrationIn, CalibrationOut, MessageOut
from app.utils.draw import encode_jpeg
from app.video.sources import build_video_source

router = APIRouter(prefix="/api/calibration", tags=["calibration"])


@router.get("/{camera_id}", response_model=CalibrationOut | None)
def get_calibration(camera_id: str, db: Session = Depends(get_db)):
    cam = db.scalar(select(Camera).where(Camera.camera_id == camera_id))
    if not cam:
        raise NotFoundError("camera not found")
    return cam.calibration


@router.post("/{camera_id}", response_model=CalibrationOut)
def save_calibration(camera_id: str, payload: CalibrationIn, db: Session = Depends(get_db)):
    cam = db.scalar(select(Camera).where(Camera.camera_id == camera_id))
    if not cam:
        raise NotFoundError("camera not found")
    if payload.method == "dual_line":
        if not payload.line_a or not payload.line_b or payload.real_distance_m <= 0:
            raise CalibrationError("dual_line requires line_a, line_b and real_distance_m > 0")
    elif payload.method == "homography":
        if len(payload.image_points) < 4 or len(payload.world_points) < 4:
            raise CalibrationError("homography requires 4 image and 4 world points")

    cal = cam.calibration or CameraCalibration(camera_pk=cam.id)
    for field, value in payload.model_dump().items():
        setattr(cal, field, value)
    cal.is_active = True
    if cal.id is None:
        db.add(cal)
    db.add(AuditLog(action="calibration.save", entity="camera", entity_id=camera_id,
                    detail={"method": payload.method}))
    db.commit()
    db.refresh(cal)
    return cal


@router.get("/{camera_id}/frame.jpg")
def calibration_frame(camera_id: str, index: int = Query(0, ge=0), db: Session = Depends(get_db)):
    cam = db.scalar(select(Camera).where(Camera.camera_id == camera_id))
    if not cam or not cam.source_uri:
        return Response(content=b"", media_type="image/jpeg")
    try:
        src = build_video_source(cam.source_type, cam.source_uri)
        frame = src.grab_frame(index)
    except Exception:
        frame = None
    if frame is None:
        return Response(content=b"", media_type="image/jpeg")
    return Response(content=encode_jpeg(frame, quality=85), media_type="image/jpeg")


@router.post("/{camera_id}/test")
def test_calibration(camera_id: str, db: Session = Depends(get_db),
                     track: list = Body(default=None)):
    """Validate a calibration by estimating speed for a sample trajectory.

    ``track`` is an optional list of [frame, t_epoch, cx, cy]. If omitted, a
    synthetic straight-line crossing at a known speed is used so the operator can
    sanity-check the geometry.
    """
    cam = db.scalar(select(Camera).where(Camera.camera_id == camera_id))
    if not cam or not cam.calibration:
        raise CalibrationError("camera has no calibration")
    cal = Calibration.from_orm(cam.calibration)
    if not cal.is_valid:
        raise CalibrationError("calibration is incomplete/invalid")
    estimator = SpeedEstimator(cal, min_confidence=0.0)

    if not track:
        # synthetic: move horizontally fully across both virtual lines (~3s)
        track = [[i, i * 0.05, 360 + i * 12, 360] for i in range(60)]
    measure = estimator.estimate_from_track([tuple(p) for p in track])
    if measure is None:
        return {"ok": False, "message": "trajectory did not cross the calibrated measurement zone"}
    return {"ok": True, "measurement": measure.to_dict()}
