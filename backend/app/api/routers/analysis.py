"""Video upload & analysis control."""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from app.database.session import get_db
from app.models import AuditLog, Camera
from app.schemas import AnalysisStart, MessageOut
from app.services.pipeline import pipeline_manager

router = APIRouter(prefix="/api", tags=["analysis"])


@router.post("/video/upload")
async def upload_video(
    file: UploadFile = File(...),
    camera_name: str = Form("Uploaded Source"),
    zone: str = Form("Uploaded"),
    create_camera: bool = Form(True),
    db: Session = Depends(get_db),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in settings.allowed_video_ext:
        raise ValidationError(f"unsupported file type '{ext}'. Allowed: {settings.allowed_video_ext}")

    dest = settings.sample_videos_dir / f"upload_{uuid.uuid4().hex[:8]}{ext}"
    size = 0
    max_bytes = settings.max_upload_mb * 1024 * 1024
    with dest.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                out.close()
                dest.unlink(missing_ok=True)
                raise ValidationError(f"file exceeds max upload size of {settings.max_upload_mb} MB")
            out.write(chunk)

    camera_id = None
    if create_camera:
        count = db.scalar(select(Camera.id).order_by(Camera.id.desc()).limit(1)) or 0
        camera_id = f"CAM-{count + 1:03d}"
        cam = Camera(camera_id=camera_id, name=camera_name, zone=zone, source_type="file",
                     source_uri=str(dest), status="offline")
        db.add(cam)
        db.add(AuditLog(action="video.upload", entity="camera", entity_id=camera_id,
                        detail={"filename": file.filename, "size_mb": round(size / 1e6, 2)}))
        db.commit()

    return {"message": "upload successful", "path": str(dest), "size_mb": round(size / 1e6, 2),
            "camera_id": camera_id}


@router.post("/analysis/start", response_model=MessageOut)
def start_analysis(payload: AnalysisStart, db: Session = Depends(get_db)):
    cam = db.scalar(select(Camera).where(Camera.camera_id == payload.camera_id))
    if not cam:
        raise NotFoundError("camera not found")
    pipeline_manager.start(cam, loop=payload.loop)
    return MessageOut(message=f"analysis started for {payload.camera_id}")


@router.post("/analysis/stop", response_model=MessageOut)
def stop_analysis(payload: AnalysisStart):
    ok = pipeline_manager.stop(payload.camera_id)
    return MessageOut(message=f"analysis {'stopped' if ok else 'not running'} for {payload.camera_id}")


@router.get("/analysis/status")
def analysis_status():
    return {"active": pipeline_manager.active_count, "pipelines": pipeline_manager.all_status()}
