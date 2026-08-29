"""Ultralytics YOLO detector (primary deep-learning backend)."""
from __future__ import annotations

import numpy as np

from app.ai.detection.base import COCO_VEHICLE_CLASSES, RELEVANT_CLASSES, Detection, VehicleDetector
from app.core.logging_config import get_logger

logger = get_logger("drishti.ai.yolo")


class YOLODetector(VehicleDetector):
    name = "yolo"
    is_deep_model = True

    def __init__(self, model_path: str = "yolov8n.pt", device: str = "cpu",
                 confidence: float = 0.35, iou: float = 0.5):
        self.model_path = model_path
        self.device = device
        self.confidence = confidence
        self.iou = iou
        self._model = None
        self._ok = False
        self._load()

    def _load(self) -> None:
        try:
            from ultralytics import YOLO  # noqa: WPS433
        except Exception as exc:  # pragma: no cover - import guard
            logger.warning("ultralytics unavailable: %s", exc)
            return
        try:
            self._model = YOLO(self.model_path)
            self._ok = True
            logger.info("YOLO loaded", extra={"extra_fields": {"model": self.model_path, "device": self.device}})
        except Exception as exc:
            logger.error("failed to load YOLO model %s: %s", self.model_path, exc)
            self._ok = False

    @property
    def available(self) -> bool:
        return self._ok

    def warmup(self) -> None:
        if not self._ok:
            return
        try:
            dummy = np.zeros((640, 640, 3), dtype=np.uint8)
            self._model.predict(dummy, verbose=False, device=self.device)
            logger.info("YOLO warmup complete")
        except Exception as exc:  # pragma: no cover
            logger.warning("YOLO warmup failed: %s", exc)

    def detect(self, frame: np.ndarray, camera_id: str = "", frame_id: int = 0) -> list[Detection]:
        if not self._ok or frame is None:
            return []
        try:
            results = self._model.predict(
                frame, verbose=False, conf=self.confidence, iou=self.iou,
                device=self.device, classes=list(RELEVANT_CLASSES.keys()),
                imgsz=320, half=(self.device != "cpu")
            )
        except Exception as exc:
            logger.error("YOLO inference error: %s", exc)
            return []

        detections: list[Detection] = []
        for res in results:
            boxes = getattr(res, "boxes", None)
            if boxes is None:
                continue
            for i in range(len(boxes)):
                cls_id = int(boxes.cls[i].item())
                name = RELEVANT_CLASSES.get(cls_id) or COCO_VEHICLE_CLASSES.get(cls_id)
                if name is None:
                    continue
                conf = float(boxes.conf[i].item())
                x1, y1, x2, y2 = (float(v) for v in boxes.xyxy[i].tolist())
                detections.append(
                    Detection(
                        vehicle_class=name, confidence=conf, bbox=(x1, y1, x2, y2),
                        camera_id=camera_id, frame_id=frame_id,
                    )
                )
        return detections
