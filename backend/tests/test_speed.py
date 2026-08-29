"""Speed math & estimation tests (spec-mandated cases + edge cases)."""
import math

import pytest

from app.ai.speed import formulas
from app.ai.speed.calibration import Calibration
from app.ai.speed.estimator import SpeedEstimator


def test_unit_conversion():
    assert formulas.mps_to_kmh(10) == pytest.approx(36.0)
    assert formulas.kmh_to_mps(36) == pytest.approx(10.0)


def test_spec_case_20m_1s_equals_72kmh():
    assert formulas.speed_kmh(20, 1.0) == pytest.approx(72.0)


def test_spec_case_50m_2s_equals_90kmh():
    assert formulas.speed_kmh(50, 2.0) == pytest.approx(90.0)


def test_example_case_25m_0_82s():
    # spec example: 25 m in 0.82 s ~= 109.76 km/h
    assert formulas.speed_kmh(25.0, 0.82) == pytest.approx(109.756, abs=0.01)


def test_zero_time_raises():
    with pytest.raises(formulas.SpeedComputationError):
        formulas.speed_kmh(20, 0)


def test_negative_time_raises():
    with pytest.raises(formulas.SpeedComputationError):
        formulas.speed_kmh(20, -1)


def test_negative_distance_raises():
    with pytest.raises(formulas.SpeedComputationError):
        formulas.speed_kmh(-5, 1)


def test_very_low_speed():
    assert formulas.speed_kmh(1, 3600) == pytest.approx(0.001)


def test_very_high_speed():
    assert formulas.speed_kmh(100, 1) == pytest.approx(360.0)


def test_excess_and_violation():
    assert formulas.excess_kmh(96, 60) == pytest.approx(36.0)
    assert formulas.excess_kmh(50, 60) == 0.0
    assert formulas.is_violation(96, 60) is True
    assert formulas.is_violation(60, 60) is False


def test_dual_line_estimation_from_track():
    cal = Calibration(method="dual_line", line_a=[[400, 0], [400, 720]],
                      line_b=[[880, 0], [880, 720]], real_distance_m=24.0, speed_limit_kmh=60)
    est = SpeedEstimator(cal, min_confidence=0.0)
    # vehicle moves at 12 px/frame, 0.05s/frame -> crosses 480px in 40 frames = 2.0s
    traj = [(i, i * 0.05, 380 + i * 12, 360) for i in range(45)]
    m = est.estimate_from_track(traj)
    assert m is not None
    # 24 m over 2.0 s = 12 m/s = 43.2 km/h
    assert m.speed_kmh == pytest.approx(43.2, abs=1.5)
    assert m.method.startswith("Calibrated")


def test_missing_calibration_returns_none():
    est = SpeedEstimator(None)
    assert est.available is False
    assert est.estimate_from_track([(0, 0, 0, 0), (1, 1, 10, 10)]) is None


def test_invalid_calibration_reports_unavailable():
    cal = Calibration(method="dual_line", line_a=[], line_b=[], real_distance_m=0)
    assert cal.is_valid is False


def test_homography_distance():
    # unit square image -> 10m x 10m world
    cal = Calibration(method="homography",
                      image_points=[[0, 0], [100, 0], [100, 100], [0, 100]],
                      world_points=[[0, 0], [10, 0], [10, 10], [0, 10]])
    assert cal.is_valid
    d = cal.world_distance((0, 0), (100, 0))
    assert d == pytest.approx(10.0, abs=0.01)
