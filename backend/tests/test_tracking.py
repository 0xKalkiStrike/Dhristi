"""Tracking & detection-parsing tests."""
import numpy as np

from app.ai.detection.base import Detection
from app.ai.detection.motion_detector import MotionDetector
from app.ai.tracking.byte_tracker import ByteTracker, iou


def _det(x, y, cls="car", conf=0.9, w=40, h=30):
    return Detection(vehicle_class=cls, confidence=conf, bbox=(x, y, x + w, y + h))


def test_iou_identical():
    assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0


def test_iou_disjoint():
    assert iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0


def test_detection_center_and_area():
    d = _det(10, 10)
    assert d.center == (30.0, 25.0)
    assert d.area == 40 * 30
    assert d.is_vehicle is True


def test_track_persistence_across_frames():
    tracker = ByteTracker(min_hits=3, max_age=5)
    tid = None
    for f in range(6):
        tracks = tracker.update([_det(100 + f * 10, 100)], frame_id=f)
        assert len(tracks) == 1
        if f == 0:
            tid = tracks[0].track_id
    # same track id maintained while moving
    assert tracks[0].track_id == tid
    assert tracks[0].confirmed is True
    assert len(tracks[0].trajectory) >= 5


def test_two_vehicles_get_distinct_ids():
    tracker = ByteTracker(min_hits=1)
    tracks = tracker.update([_det(50, 50), _det(300, 300)], frame_id=0)
    ids = {t.track_id for t in tracker.update([_det(55, 50), _det(305, 300)], frame_id=1)}
    assert len(ids) == 2


def test_track_ages_out_when_lost():
    tracker = ByteTracker(min_hits=1, max_age=2)
    tracker.update([_det(100, 100)], frame_id=0)
    tracker.update([], frame_id=1)
    tracker.update([], frame_id=2)
    active = tracker.update([], frame_id=3)
    assert active == []


def test_motion_detector_finds_moving_blob():
    det = MotionDetector(min_area=200)
    bg = np.zeros((240, 320, 3), dtype=np.uint8)
    # prime background
    for _ in range(5):
        det.detect(bg)
    frame = bg.copy()
    frame[80:140, 120:200] = 255       # a bright moving block
    results = det.detect(frame)
    assert any(r.area > 200 for r in results)
