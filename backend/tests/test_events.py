"""Traffic-event detector tests."""
import datetime as dt

from app.ai.speed.estimator import SpeedMeasurement
from app.ai.tracking.base import TrackState
from app.events.detectors import EventEngine, _point_in_polygon


def _track(tid="TRACK-000001", vx=5.0, vy=0.0):
    now = dt.datetime.now(dt.timezone.utc)
    t = TrackState(track_id=tid, vehicle_class="car", confidence=0.9, bbox=(0, 0, 40, 30),
                   first_frame=0, last_frame=10, first_seen=now, last_seen=now, hits=5,
                   velocity=(vx, vy), confirmed=True)
    for i in range(10):
        t.trajectory.append((i, i * 0.1, i * vx, i * vy))
    return t


def test_overspeed_event_fires():
    eng = EventEngine()
    m = SpeedMeasurement(speed_kmh=96, distance_m=24, elapsed_s=0.9, method="dual", confidence=0.94,
                         speed_limit_kmh=60, excess_kmh=36, is_violation=True)
    evt = eng.check_overspeed(_track(), m)
    assert evt is not None
    assert evt.event_type == "overspeed"
    assert "96" in evt.reason and "60" in evt.reason
    assert evt.severity == "critical"


def test_overspeed_not_fired_when_within_limit():
    eng = EventEngine()
    m = SpeedMeasurement(speed_kmh=55, distance_m=24, elapsed_s=1.5, method="dual", confidence=0.9,
                         speed_limit_kmh=60, excess_kmh=0, is_violation=False)
    assert eng.check_overspeed(_track(), m) is None


def test_overspeed_dedupes_per_track():
    eng = EventEngine()
    m = SpeedMeasurement(speed_kmh=96, distance_m=24, elapsed_s=0.9, method="dual", confidence=0.94,
                         speed_limit_kmh=60, excess_kmh=36, is_violation=True)
    t = _track()
    assert eng.check_overspeed(t, m) is not None
    assert eng.check_overspeed(t, m) is None   # second time deduped


def test_wrong_way_detection():
    eng = EventEngine(allowed_direction="right")
    evt = eng.check_wrong_way(_track(vx=-6.0))     # moving left against allowed right
    assert evt is not None
    assert evt.event_type == "wrong_way"


def test_wrong_way_ignored_when_correct_direction():
    eng = EventEngine(allowed_direction="right")
    assert eng.check_wrong_way(_track(vx=6.0)) is None


def test_stopped_vehicle_detection():
    eng = EventEngine(stopped_frames=3)
    t = _track(vx=0.0, vy=0.0)
    fired = None
    for _ in range(5):
        fired = eng.check_stopped(t) or fired
    assert fired is not None
    assert fired.event_type == "stopped_vehicle"


def test_congestion_threshold():
    eng = EventEngine(congestion_threshold=5)
    assert eng.check_congestion("CAM-001", 3, 0) is None
    assert eng.check_congestion("CAM-001", 8, 0) is not None


def test_point_in_polygon():
    poly = [[0, 0], [10, 0], [10, 10], [0, 10]]
    assert _point_in_polygon((5, 5), poly) is True
    assert _point_in_polygon((15, 5), poly) is False
