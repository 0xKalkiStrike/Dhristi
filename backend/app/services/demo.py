"""One-click demo setup: bundled synthetic multi-camera scenes.

Demo pipelines run the classical motion detector (the synthetic blobs are not
COCO objects); the UI labels this clearly. Real footage uses YOLO automatically.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging_config import get_logger
from app.models import Camera, CameraCalibration
from app.services.pipeline import pipeline_manager
from app.utils.sample_video import build_demo_dataset

logger = get_logger("drishti.demo")


def ensure_sample_videos() -> list[dict]:
    out_dir: Path = settings.sample_videos_dir
    existing = list(out_dir.glob("cam-*.mp4"))
    dataset = build_demo_dataset(out_dir) if len(existing) < 4 else _dataset_from_disk(out_dir)
    return dataset


def _dataset_from_disk(out_dir: Path) -> list[dict]:
    # Rebuild metadata deterministically (same seed) without re-rendering videos.
    from app.utils.sample_video import build_demo_dataset as _b
    # If videos exist we still want metadata; regenerate metadata cheaply by
    # re-running the generator only when missing. Here videos exist, so just
    # return the canonical dataset definition (videos already on disk).
    return _b(out_dir)


def setup_demo(db: Session) -> list[dict]:
    dataset = ensure_sample_videos()
    for cam in dataset:
        existing = db.scalar(select(Camera).where(Camera.camera_id == cam["camera_id"]))
        if existing is None:
            existing = Camera(camera_id=cam["camera_id"], name=cam["name"], zone=cam["zone"],
                              location=cam["location"], source_type="file", source_uri=cam["source_uri"],
                              enabled=True, status="offline")
            db.add(existing)
            db.flush()
        else:
            existing.source_uri = cam["source_uri"]
            existing.name = cam["name"]
            existing.zone = cam["zone"]
            existing.location = cam["location"]
        # calibration
        cal = existing.calibration
        payload = cam["calibration"]
        if cal is None:
            cal = CameraCalibration(camera_pk=existing.id)
            db.add(cal)
        for k, v in payload.items():
            setattr(cal, k, v)
        cal.is_active = True
    db.commit()
    logger.info("demo dataset ready", extra={"extra_fields": {"cameras": len(dataset)}})
    return dataset


def start_demo(db: Session) -> dict:
    dataset = setup_demo(db)
    started = []
    for cam in dataset:
        camera = db.scalar(select(Camera).where(Camera.camera_id == cam["camera_id"]))
        if camera:
            pipeline_manager.start(camera, loop=True, demo_detector="motion")
            started.append(camera.camera_id)
    return {"cameras": started, "count": len(started),
            "note": "Demo pipelines use the classical motion detector on synthetic scenes; "
                    "OCR reads real rendered plates; speed uses real calibration."}


def stop_demo() -> dict:
    pipeline_manager.stop_all()
    return {"stopped": True}
