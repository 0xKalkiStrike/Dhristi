"""Live-camera device discovery & connection (webcam / Bluetooth / IP).

Lets an operator connect a REAL camera for live analysis instead of demo data.
Connected live cameras run the real detector (YOLO when available).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.database.session import get_db
from app.models import AuditLog, Camera
from app.schemas import CameraOut
from app.services.pipeline import pipeline_manager
from app.video import devices as devsvc
from app.video.push import push_frame

router = APIRouter(prefix="/api/devices", tags=["devices"])
_pool = ThreadPoolExecutor(max_workers=2)


@router.get("/video")
async def video_devices():
    """List OS camera devices (webcams and OS-exposed Bluetooth cameras)."""
    import asyncio
    return await asyncio.get_running_loop().run_in_executor(_pool, devsvc.list_video_devices)


@router.get("/bluetooth")
async def bluetooth_devices():
    """List paired/known Bluetooth devices (cameras among them can be connected)."""
    import asyncio
    return await asyncio.get_running_loop().run_in_executor(_pool, devsvc.list_bluetooth_devices)


@router.get("/probe")
async def probe(index: int = Query(0, ge=0, le=15)):
    """Try to open a local video device by index and grab one frame (bounded)."""
    import asyncio
    return await asyncio.get_running_loop().run_in_executor(_pool, devsvc.probe_video_index, index)


class ConnectRequest(BaseModel):
    name: str
    source_type: str            # webcam | bluetooth | rtsp | browser
    index: int | None = None    # for webcam/bluetooth
    url: str | None = None      # for rtsp / ip camera
    zone: str = "Live"
    location: str = ""
    start: bool = True


@router.post("/connect", response_model=CameraOut)
def connect_camera(req: ConnectRequest, db: Session = Depends(get_db)):
    st = req.source_type.lower()
    count = db.scalar(select(Camera.id).order_by(Camera.id.desc()).limit(1)) or 0
    camera_id = f"CAM-{count + 1:03d}"

    if st in ("webcam", "bluetooth"):
        if req.index is None:
            raise ValidationError(f"{st} requires a device 'index'")
        source_uri = str(req.index)
    elif st in ("rtsp", "ip"):
        st = "rtsp"
        if not req.url:
            raise ValidationError("rtsp/ip camera requires a 'url'")
        url = req.url.strip()
        if url.startswith(("http://", "https://")):
            from urllib.parse import urlparse
            p = urlparse(url)
            if not p.path or p.path == "/":
                url = f"{url.rstrip('/')}/video"
        source_uri = url
    elif st in ("browser", "push"):
        # This-device camera: browser pushes frames to /api/devices/ingest/{camera_id}
        st = "browser"
        source_uri = camera_id
    else:
        raise ValidationError(f"unsupported live source_type '{req.source_type}'")

    cam = Camera(camera_id=camera_id, name=req.name, zone=req.zone, location=req.location,
                 source_type=st, source_uri=source_uri, status="offline", enabled=True)
    db.add(cam)
    db.add(AuditLog(action="camera.connect_live", entity="camera", entity_id=camera_id,
                    detail={"source_type": st, "live": True}))
    db.commit()
    db.refresh(cam)

    if req.start:
        # live camera -> real detector (no demo motion detector)
        pipeline_manager.start(cam, loop=False, demo_detector=None)

    from app.api.routers.cameras import _to_out
    return _to_out(cam)


@router.post("/ingest/{camera_id}", status_code=202)
async def ingest_frame(camera_id: str, request: Request):
    """Receive one JPEG frame (raw body) from a browser camera and feed the pipeline."""
    body = await request.body()
    if not body:
        raise ValidationError("empty frame body")
    arr = np.frombuffer(body, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValidationError("could not decode frame (expected JPEG bytes)")
    p = pipeline_manager.get(camera_id)
    if not p or not p.is_alive():
        raise NotFoundError(f"no live pipeline for {camera_id}; connect the camera first")
    push_frame(camera_id, img)
    return {"ok": True}

