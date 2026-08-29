"""Vehicle detection abstraction.

``VehicleDetector`` is the interface every detector backend implements so the
rest of the pipeline is decoupled from any single model.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

# COCO class ids that are road vehicles / relevant objects
COCO_VEHICLE_CLASSES = {
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}
# Objects we also surface but treat separately from "vehicles"
RELEVANT_CLASSES = {**COCO_VEHICLE_CLASSES, 0: "person"}

VEHICLE_CLASS_NAMES = set(COCO_VEHICLE_CLASSES.values())


@dataclass
class Detection:
    """A single object detection in one frame."""

    vehicle_class: str
    confidence: float
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2
    detection_id: str = ""
    camera_id: str = ""
    frame_id: int = 0
    tracking_id: Optional[str] = None
    extra: dict = field(default_factory=dict)

    @property
    def center(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    @property
    def width(self) -> float:
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self) -> float:
        return self.bbox[3] - self.bbox[1]

    @property
    def area(self) -> float:
        return max(0.0, self.width) * max(0.0, self.height)

    @property
    def is_vehicle(self) -> bool:
        return self.vehicle_class in VEHICLE_CLASS_NAMES

    def to_dict(self) -> dict:
        return {
            "detection_id": self.detection_id,
            "camera_id": self.camera_id,
            "frame_id": self.frame_id,
            "vehicle_class": self.vehicle_class,
            "confidence": round(float(self.confidence), 4),
            "bbox": [round(float(v), 2) for v in self.bbox],
            "center": [round(float(v), 2) for v in self.center],
            "tracking_id": self.tracking_id,
        }


class VehicleDetector(abc.ABC):
    """Interface for all detector backends."""

    name: str = "base"
    is_deep_model: bool = False

    @abc.abstractmethod
    def detect(self, frame: np.ndarray, camera_id: str = "", frame_id: int = 0) -> list[Detection]:
        """Return detections for a single BGR frame."""

    def warmup(self) -> None:  # optional
        pass

    @property
    def available(self) -> bool:
        return True

    def info(self) -> dict:
        return {"name": self.name, "deep_model": self.is_deep_model, "available": self.available}
