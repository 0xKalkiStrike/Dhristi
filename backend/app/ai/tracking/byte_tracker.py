"""ByteTrack-style multi-object tracker.

Two-stage association (high- then low-confidence detections) with linear-motion
prediction and IoU matching via the Hungarian algorithm. Handles brief
occlusion by keeping lost tracks alive up to ``max_age`` frames.
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

import numpy as np
from scipy.optimize import linear_sum_assignment

from app.ai.detection.base import Detection
from app.ai.tracking.base import TrackState, VehicleTracker


def iou(a: tuple, b: tuple) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


class ByteTracker(VehicleTracker):
    name = "bytetrack"

    def __init__(self, high_thresh: float = 0.5, low_thresh: float = 0.2,
                 max_age: int = 30, min_hits: int = 3, iou_match: float = 0.3):
        self.high_thresh = high_thresh
        self.low_thresh = low_thresh
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_match = iou_match
        self._tracks: list[TrackState] = []
        self._next_id = 1

    def reset(self) -> None:
        self._tracks = []
        self._next_id = 1

    def _new_id(self) -> str:
        tid = f"TRACK-{self._next_id:06d}"
        self._next_id += 1
        return tid

    @staticmethod
    def _predict(track: TrackState) -> tuple:
        vx, vy = track.velocity
        x1, y1, x2, y2 = track.bbox
        return (x1 + vx, y1 + vy, x2 + vx, y2 + vy)

    def _match(self, tracks: list[TrackState], dets: list[Detection]):
        if not tracks or not dets:
            return [], list(range(len(tracks))), list(range(len(dets)))
        cost = np.zeros((len(tracks), len(dets)), dtype=np.float32)
        for i, t in enumerate(tracks):
            pred = self._predict(t)
            for j, d in enumerate(dets):
                cost[i, j] = 1.0 - iou(pred, d.bbox)
        rows, cols = linear_sum_assignment(cost)
        matches, um_t, um_d = [], [], []
        matched_t, matched_d = set(), set()
        for r, c in zip(rows, cols):
            if cost[r, c] <= 1.0 - self.iou_match:
                matches.append((r, c))
                matched_t.add(r)
                matched_d.add(c)
        um_t = [i for i in range(len(tracks)) if i not in matched_t]
        um_d = [j for j in range(len(dets)) if j not in matched_d]
        return matches, um_t, um_d

    def _update_track(self, track: TrackState, det: Detection, frame_id: int,
                      ts: dt.datetime, t_epoch: float) -> None:
        old_cx, old_cy = track.center
        # Exponential Moving Average (EMA) smoothing for rock-solid, jitter-free bounding boxes
        alpha = 0.75
        track.bbox = (
            alpha * det.bbox[0] + (1 - alpha) * track.bbox[0],
            alpha * det.bbox[1] + (1 - alpha) * track.bbox[1],
            alpha * det.bbox[2] + (1 - alpha) * track.bbox[2],
            alpha * det.bbox[3] + (1 - alpha) * track.bbox[3],
        )
        ncx, ncy = track.center
        # Smooth velocity estimation
        vx = alpha * (ncx - old_cx) + (1 - alpha) * track.velocity[0]
        vy = alpha * (ncy - old_cy) + (1 - alpha) * track.velocity[1]
        track.velocity = (vx, vy)
        track.last_frame = frame_id
        track.last_seen = ts
        track.confidence = det.confidence
        track.hits += 1
        track.age = 0
        track.class_votes[det.vehicle_class] = track.class_votes.get(det.vehicle_class, 0) + 1
        track.vehicle_class = track.dominant_class()
        track.trajectory.append((frame_id, t_epoch, ncx, ncy))
        if track.hits >= self.min_hits:
            track.confirmed = True

    def update(self, detections: list[Detection], frame_id: int,
               timestamp: Optional[dt.datetime] = None, time_s: Optional[float] = None) -> list[TrackState]:
        ts = timestamp or dt.datetime.now(dt.timezone.utc)
        t_epoch = time_s if time_s is not None else ts.timestamp()
        high = [d for d in detections if d.confidence >= self.high_thresh]
        low = [d for d in detections if self.low_thresh <= d.confidence < self.high_thresh]

        # Stage 1: match all tracks with high-confidence detections
        matches, um_t, um_d = self._match(self._tracks, high)
        for ti, di in matches:
            self._update_track(self._tracks[ti], high[di], frame_id, ts, t_epoch)

        # Stage 2: match remaining tracks with low-confidence detections
        remaining_tracks = [self._tracks[i] for i in um_t]
        matches2, um_t2, _ = self._match(remaining_tracks, low)
        for ti, di in matches2:
            self._update_track(remaining_tracks[ti], low[di], frame_id, ts, t_epoch)
        matched_remaining = {ti for ti, _ in matches2}
        still_unmatched = [remaining_tracks[i] for i in range(len(remaining_tracks)) if i not in matched_remaining]

        # Age unmatched tracks and coast their predicted positions with velocity decay
        for t in still_unmatched:
            t.age += 1
            if t.age <= self.max_age:
                t.bbox = self._predict(t)
                t.velocity = (t.velocity[0] * 0.92, t.velocity[1] * 0.92)  # gentle decay
                ncx, ncy = t.center
                t.trajectory.append((frame_id, t_epoch, ncx, ncy))


        # Create new tracks for unmatched high-confidence detections
        for di in um_d:
            d = high[di]
            cx, cy = d.center
            t = TrackState(
                track_id=self._new_id(), vehicle_class=d.vehicle_class, confidence=d.confidence,
                bbox=d.bbox, first_frame=frame_id, last_frame=frame_id, first_seen=ts, last_seen=ts,
                class_votes={d.vehicle_class: 1},
            )
            t.trajectory.append((frame_id, t_epoch, cx, cy))
            self._tracks.append(t)

        # Drop expired tracks
        self._tracks = [t for t in self._tracks if t.age <= self.max_age]

        # Attach tracking ids to detections (for persistence)
        for t in self._tracks:
            if t.age == 0:
                cx, cy = t.center
                for d in detections:
                    if d.tracking_id is None and abs(d.center[0] - cx) < 1e-3 and abs(d.center[1] - cy) < 1e-3:
                        d.tracking_id = t.track_id

        # Return tracks that are actively observed or recently coasting (smooth visuals)
        max_visible_age = 5
        return [t for t in self._tracks if t.age <= max_visible_age]

    @property
    def active_tracks(self) -> list[TrackState]:
        return [t for t in self._tracks if t.age <= 5]

