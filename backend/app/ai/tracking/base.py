"""Tracking abstractions and the in-memory Track object."""
from __future__ import annotations

import abc
import datetime as dt
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from app.ai.detection.base import Detection


@dataclass
class TrackState:
    track_id: str
    vehicle_class: str
    confidence: float
    bbox: tuple[float, float, float, float]
    first_frame: int
    last_frame: int
    first_seen: dt.datetime
    last_seen: dt.datetime
    hits: int = 1
    age: int = 0                       # frames since last matched
    velocity: tuple[float, float] = (0.0, 0.0)
    trajectory: deque = field(default_factory=lambda: deque(maxlen=256))  # (frame, t, cx, cy)
    class_votes: dict = field(default_factory=dict)
    confirmed: bool = False

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

    def dominant_class(self) -> str:
        if not self.class_votes:
            return self.vehicle_class
        return max(self.class_votes.items(), key=lambda kv: kv[1])[0]


class VehicleTracker(abc.ABC):
    name = "base"

    @abc.abstractmethod
    def update(self, detections: list[Detection], frame_id: int,
               timestamp: Optional[dt.datetime] = None) -> list[TrackState]:
        """Advance the tracker by one frame; return currently active tracks."""

    @abc.abstractmethod
    def reset(self) -> None:
        ...
