"""Pure speed math — deterministic and unit-tested.

Never divides by zero; guards invalid inputs explicitly.
"""
from __future__ import annotations

MPS_TO_KMH = 3.6


class SpeedComputationError(ValueError):
    pass


def mps_to_kmh(mps: float) -> float:
    return float(mps) * MPS_TO_KMH


def kmh_to_mps(kmh: float) -> float:
    return float(kmh) / MPS_TO_KMH


def speed_mps(distance_m: float, elapsed_s: float) -> float:
    """Speed in metres/second from distance & elapsed time."""
    if elapsed_s is None or elapsed_s <= 0:
        raise SpeedComputationError("elapsed time must be > 0")
    if distance_m is None or distance_m < 0:
        raise SpeedComputationError("distance must be >= 0")
    return float(distance_m) / float(elapsed_s)


def speed_kmh(distance_m: float, elapsed_s: float) -> float:
    """Speed in km/h from distance (m) and elapsed time (s)."""
    return mps_to_kmh(speed_mps(distance_m, elapsed_s))


def excess_kmh(speed: float, limit: float) -> float:
    return max(0.0, float(speed) - float(limit))


def is_violation(speed: float, limit: float, tolerance: float = 0.0) -> bool:
    return float(speed) > float(limit) + float(tolerance)
