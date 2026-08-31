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
            pred_cx = (pred[0] + pred[2]) / 2.0
            pred_cy = (pred[1] + pred[3]) / 2.0
            pred_diag = max(1.0, ((pred[2] - pred[0]) ** 2 + (pred[3] - pred[1]) ** 2) ** 0.5)
            for j, d in enumerate(dets):
                det_cx, det_cy = d.center
                c_dist = ((pred_cx - det_cx) ** 2 + (pred_cy - det_cy) ** 2) ** 0.5
                iou_val = iou(pred, d.bbox)
                # Distance-IoU: overlap penalized by normalized centroid distance (vital for 100+ km/h tracking)
                diou = iou_val - (c_dist / (2.5 * pred_diag))
                cost[i, j] = 1.0 - max(0.0, diou)
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
        det.tracking_id = track.track_id
        old_cx, old_cy = track.center
        
        # Adaptive Exponential Moving Average: smooth out sensor jitter while tracking real motion
        det_cx = (det.bbox[0] + det.bbox[2]) / 2.0
        det_cy = (det.bbox[1] + det.bbox[3]) / 2.0
        det_w = det.bbox[2] - det.bbox[0]
        det_h = det.bbox[3] - det.bbox[1]
        
        trk_w = track.bbox[2] - track.bbox[0]
        trk_h = track.bbox[3] - track.bbox[1]
        
        dist = ((det_cx - old_cx) ** 2 + (det_cy - old_cy) ** 2) ** 0.5
        # High responsiveness on large/high-speed movement (100+ km/h), rock-solid stability on small fluctuations
        pos_alpha = 0.85 if dist > 35.0 else (0.65 if dist > 15.0 else 0.45)
        size_alpha = 0.35  # Keep box size steady and free from flickering
        
        smooth_cx = pos_alpha * det_cx + (1.0 - pos_alpha) * (old_cx + track.velocity[0])
        smooth_cy = pos_alpha * det_cy + (1.0 - pos_alpha) * (old_cy + track.velocity[1])
        smooth_w = size_alpha * det_w + (1.0 - size_alpha) * trk_w
        smooth_h = size_alpha * det_h + (1.0 - size_alpha) * trk_h
        
        track.bbox = (
            smooth_cx - smooth_w / 2.0,
            smooth_cy - smooth_h / 2.0,
            smooth_cx + smooth_w / 2.0,
            smooth_cy + smooth_h / 2.0,
        )
        
        ncx, ncy = track.center
        # Smooth velocity estimation
        vel_alpha = 0.4
        vx = vel_alpha * (ncx - old_cx) + (1.0 - vel_alpha) * track.velocity[0]
        vy = vel_alpha * (ncy - old_cy) + (1.0 - vel_alpha) * track.velocity[1]
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

    def update(self, detections: Optional[list[Detection]], frame_id: int,
               timestamp: Optional[dt.datetime] = None, time_s: Optional[float] = None,
               is_detect_frame: bool = True) -> list[TrackState]:
        ts = timestamp or dt.datetime.now(dt.timezone.utc)
        t_epoch = time_s if time_s is not None else ts.timestamp()

        # If this is a tracking-only frame (detector was skipped for performance),
        # smoothly coast all active tracks without penalizing their age or killing momentum.
        if not is_detect_frame or detections is None:
            for t in self._tracks:
                if t.age <= self.max_age:
                    t.bbox = self._predict(t)
                    ncx, ncy = t.center
                    t.trajectory.append((frame_id, t_epoch, ncx, ncy))
                    t.last_frame = frame_id
            return [t for t in self._tracks if t.age <= 5]

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

        # Age unmatched tracks and coast their predicted positions with gentle velocity decay
        for t in still_unmatched:
            t.age += 1
            if t.age <= self.max_age:
                t.bbox = self._predict(t)
                t.velocity = (t.velocity[0] * 0.95, t.velocity[1] * 0.95)
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
            d.tracking_id = t.track_id
            t.trajectory.append((frame_id, t_epoch, cx, cy))
            self._tracks.append(t)

        # Drop expired tracks
        self._tracks = [t for t in self._tracks if t.age <= self.max_age]

        # Return tracks that are actively observed or recently coasting (smooth visuals)
        max_visible_age = 5
        return [t for t in self._tracks if t.age <= max_visible_age]

    @property
    def active_tracks(self) -> list[TrackState]:
        return [t for t in self._tracks if t.age <= 5]

