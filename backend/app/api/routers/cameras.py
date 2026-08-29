"""Camera management, control and live preview."""
from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.database.session import get_db
from app.models import AuditLog, Camera
from app.schemas import CameraCreate, CameraOut, CameraUpdate, MessageOut
from app.services.pipeline import pipeline_manager

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


def _to_out(cam: Camera) -> CameraOut:
    return CameraOut(
        id=cam.id, camera_id=cam.camera_id, name=cam.name, location=cam.location, zone=cam.zone,
        orientation=cam.orientation, source_type=cam.source_type, has_source=bool(cam.source_uri),
        latitude=cam.latitude, longitude=cam.longitude, enabled=cam.enabled, status=cam.status,
        fps=cam.fps, last_environment=cam.last_environment, ai_status=cam.ai_status,
        has_calibration=cam.calibration is not None,
    )


def _next_camera_id(db: Session) -> str:
    count = db.scalar(select(Camera.id).order_by(Camera.id.desc()).limit(1)) or 0
    return f"CAM-{count + 1:03d}"


@router.get("", response_model=list[CameraOut])
def list_cameras(db: Session = Depends(get_db)):
    cams = db.scalars(select(Camera).order_by(Camera.camera_id)).all()
    return [_to_out(c) for c in cams]


@router.post("", response_model=CameraOut, status_code=201)
def create_camera(payload: CameraCreate, db: Session = Depends(get_db)):
    cam = Camera(
        camera_id=payload.camera_id or _next_camera_id(db), name=payload.name, location=payload.location,
        zone=payload.zone, orientation=payload.orientation, source_type=payload.source_type,
        source_uri=payload.source_uri, latitude=payload.latitude, longitude=payload.longitude,
        enabled=payload.enabled, status="offline",
    )
    db.add(cam)
    db.add(AuditLog(action="camera.create", entity="camera", entity_id=cam.camera_id,
                    detail={"name": cam.name, "source_type": cam.source_type}))
    db.commit()
    db.refresh(cam)
    return _to_out(cam)


@router.get("/{camera_id}", response_model=CameraOut)
def get_camera(camera_id: str, db: Session = Depends(get_db)):
    cam = db.scalar(select(Camera).where(Camera.camera_id == camera_id))
    if not cam:
        raise NotFoundError("camera not found")
    return _to_out(cam)


@router.patch("/{camera_id}", response_model=CameraOut)
def update_camera(camera_id: str, payload: CameraUpdate, db: Session = Depends(get_db)):
    cam = db.scalar(select(Camera).where(Camera.camera_id == camera_id))
    if not cam:
        raise NotFoundError("camera not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(cam, field, value)
    db.add(AuditLog(action="camera.update", entity="camera", entity_id=camera_id))
    db.commit()
    db.refresh(cam)
    return _to_out(cam)


@router.delete("/{camera_id}", response_model=MessageOut)
def delete_camera(camera_id: str, db: Session = Depends(get_db)):
    cam = db.scalar(select(Camera).where(Camera.camera_id == camera_id))
    if not cam:
        raise NotFoundError("camera not found")
    pipeline_manager.stop(camera_id)
    db.delete(cam)
    db.add(AuditLog(action="camera.delete", entity="camera", entity_id=camera_id))
    db.commit()
    return MessageOut(message=f"camera {camera_id} deleted")


# A lightweight 1x1 black JPEG for empty/standby streams
_STANDBY_JPEG = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06"
    b"\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
    b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00"
    b"\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01"
    b"\x01\x00\x00?\x00\xbf\x00\xff\xd9"
)


@router.post("/{camera_id}/start", response_model=MessageOut)
def start_camera(camera_id: str, loop: bool = False, detector: str | None = None,
                 db: Session = Depends(get_db)):
    cam = db.scalar(select(Camera).where(Camera.camera_id == camera_id))
    if not cam:
        raise NotFoundError("camera not found")
    if cam.source_type == "file" and not cam.source_uri:
        raise NotFoundError(f"camera {camera_id} has no source file configured")
    try:
        pipeline_manager.start(cam, loop=loop, demo_detector=detector)
        db.add(AuditLog(action="camera.start", entity="camera", entity_id=camera_id))
        db.commit()
    except Exception as exc:
        db.rollback()
        raise NotFoundError(f"failed to start camera {camera_id}: {exc}")
    return MessageOut(message=f"analysis started for {camera_id}",
                      data={"detector": detector or "auto", "loop": loop})


@router.post("/{camera_id}/stop", response_model=MessageOut)
def stop_camera(camera_id: str, db: Session = Depends(get_db)):
    ok = pipeline_manager.stop(camera_id)
    db.add(AuditLog(action="camera.stop", entity="camera", entity_id=camera_id))
    db.commit()
    return MessageOut(message=f"analysis {'stopped' if ok else 'was not running'} for {camera_id}")


@router.get("/{camera_id}/status")
def camera_status(camera_id: str):
    status = pipeline_manager.status(camera_id)
    return status or {"camera_id": camera_id, "running": False}


@router.get("/{camera_id}/frame.jpg")
def camera_frame(camera_id: str):
    p = pipeline_manager.get(camera_id)
    if not p or not p.latest_jpeg:
        return Response(content=_STANDBY_JPEG, media_type="image/jpeg",
                        headers={"Cache-Control": "no-store"})
    return Response(content=p.latest_jpeg, media_type="image/jpeg",
                    headers={"Cache-Control": "no-store"})


@router.get("/{camera_id}/stream")
async def camera_stream(camera_id: str, db: Session = Depends(get_db)):
    """High-performance multipart MJPEG stream for real-time, zero-lag browser playback."""
    cam = db.scalar(select(Camera).where(Camera.camera_id == camera_id))
    if not cam:
        raise NotFoundError("camera not found")

    # If camera has a source and isn't running, auto-start in background
    p = pipeline_manager.get(camera_id)
    if (not p or not p.is_alive()) and cam.source_uri and cam.enabled:
        try:
            pipeline_manager.start(cam, loop=True)
        except Exception:
            pass

    async def frame_generator():
        last_seq = -1
        # Yield standby frame immediately so browser connects instantly
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n"
            b"Content-Length: " + str(len(_STANDBY_JPEG)).encode("ascii") + b"\r\n\r\n"
            + _STANDBY_JPEG + b"\r\n"
        )
        while True:
            p = pipeline_manager.get(camera_id)
            if p and p.is_alive():
                seq, jpeg = await asyncio.to_thread(p.get_latest_frame, last_seq, 0.15)
                if seq != last_seq and jpeg:
                    last_seq = seq
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n"
                        b"Content-Length: " + str(len(jpeg)).encode("ascii") + b"\r\n\r\n"
                        + jpeg + b"\r\n"
                    )
            else:
                # Camera standby/offline: yield frame occasionally to keep HTTP connection alive
                await asyncio.sleep(1.0)
                curr_jpeg = p.latest_jpeg if p and p.latest_jpeg else _STANDBY_JPEG
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: " + str(len(curr_jpeg)).encode("ascii") + b"\r\n\r\n"
                    + curr_jpeg + b"\r\n"
                )

    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "Connection": "close",
        },
    )


