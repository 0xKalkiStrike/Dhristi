"""Detector factory — selects the best available backend."""
from __future__ import annotations

from app.ai.detection.base import VehicleDetector
from app.ai.detection.motion_detector import MotionDetector
from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger("drishti.ai.factory")


def resolve_device(requested: str = "auto") -> str:
    if requested == "cpu":
        return "cpu"
    try:
        import torch
        if requested in ("auto", "cuda") and torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def build_detector(backend: str | None = None, device: str | None = None) -> VehicleDetector:
    backend = (backend or settings.detector_backend).lower()
    device = resolve_device(device or settings.ai_device)

    def _yolo():
        from app.ai.detection.yolo_detector import YOLODetector
        d = YOLODetector(settings.yolo_model, device, settings.detection_confidence, settings.detection_iou)
        return d if d.available else None

    def _tv():
        from app.ai.detection.torchvision_detector import TorchvisionDetector
        d = TorchvisionDetector(device, settings.detection_confidence)
        return d if d.available else None

    if backend == "yolo":
        d = _yolo()
        if d:
            return d
        logger.warning("yolo requested but unavailable; falling back")
    elif backend == "torchvision":
        d = _tv()
        if d:
            return d
    elif backend == "motion":
        return MotionDetector()
    elif backend == "null":
        return _NullDetector()

    if backend == "auto":
        d = _yolo() or _tv()
        if d:
            return d
        logger.warning("no deep detector available; using classical motion detector")
    return MotionDetector()


class _NullDetector(VehicleDetector):
    name = "null"

    def detect(self, frame, camera_id: str = "", frame_id: int = 0):
        return []

    @property
    def available(self) -> bool:
        return False
