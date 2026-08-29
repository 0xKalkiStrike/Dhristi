"""Torchvision detector (SSDLite/Faster-RCNN) — deep-learning fallback.

Used when ultralytics is unavailable but torch/torchvision are present. Uses
COCO-pretrained weights so it detects the same vehicle classes as YOLO.
"""
from __future__ import annotations

import numpy as np

from app.ai.detection.base import RELEVANT_CLASSES, Detection, VehicleDetector
from app.core.logging_config import get_logger

logger = get_logger("drishti.ai.torchvision")


class TorchvisionDetector(VehicleDetector):
    name = "torchvision"
    is_deep_model = True

    def __init__(self, device: str = "cpu", confidence: float = 0.35):
        self.device = device
        self.confidence = confidence
        self._model = None
        self._torch = None
        self._ok = False
        self._load()

    def _load(self) -> None:
        try:
            import torch
            from torchvision.models.detection import (
                ssdlite320_mobilenet_v3_large,
                SSDLite320_MobileNet_V3_Large_Weights,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("torchvision detector unavailable: %s", exc)
            return
        try:
            weights = SSDLite320_MobileNet_V3_Large_Weights.DEFAULT
            self._model = ssdlite320_mobilenet_v3_large(weights=weights)
            self._model.eval().to(self.device)
            self._torch = torch
            self._ok = True
            logger.info("Torchvision SSDLite loaded", extra={"extra_fields": {"device": self.device}})
        except Exception as exc:
            logger.error("failed to load torchvision detector: %s", exc)

    @property
    def available(self) -> bool:
        return self._ok

    def detect(self, frame: np.ndarray, camera_id: str = "", frame_id: int = 0) -> list[Detection]:
        if not self._ok or frame is None:
            return []
        torch = self._torch
        try:
            rgb = frame[:, :, ::-1].copy()
            tensor = torch.from_numpy(rgb).permute(2, 0, 1).float().div(255.0).to(self.device)
            with torch.no_grad():
                out = self._model([tensor])[0]
        except Exception as exc:
            logger.error("torchvision inference error: %s", exc)
            return []

        dets: list[Detection] = []
        boxes = out["boxes"].cpu().numpy()
        labels = out["labels"].cpu().numpy()
        scores = out["scores"].cpu().numpy()
        for box, label, score in zip(boxes, labels, scores):
            if score < self.confidence:
                continue
            name = RELEVANT_CLASSES.get(int(label))
            if name is None:
                continue
            x1, y1, x2, y2 = (float(v) for v in box)
            dets.append(Detection(vehicle_class=name, confidence=float(score),
                                  bbox=(x1, y1, x2, y2), camera_id=camera_id, frame_id=frame_id))
        return dets
