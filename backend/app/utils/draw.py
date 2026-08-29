"""Frame annotation helpers for the live camera tiles."""
from __future__ import annotations

import cv2
import numpy as np

_CLASS_COLORS = {
    "car": (0, 200, 255), "truck": (255, 120, 0), "bus": (255, 0, 180),
    "motorcycle": (0, 255, 120), "bicycle": (120, 255, 0), "person": (200, 200, 200),
}


def draw_overlays(frame: np.ndarray, tracks, calibration=None, environment: str = "day",
                  backend: str = "", camera_name: str = "") -> np.ndarray:
    out = frame.copy()
    h, w = out.shape[:2]

    # calibration lines
    if calibration is not None and getattr(calibration, "method", "") == "dual_line" and calibration.line_a:
        for line, col in ((calibration.line_a, (0, 255, 255)), (calibration.line_b, (0, 165, 255))):
            if line and len(line) == 2:
                cv2.line(out, tuple(map(int, line[0])), tuple(map(int, line[1])), col, 2)

    for t in tracks:
        x1, y1, x2, y2 = (int(v) for v in t.bbox)
        color = _CLASS_COLORS.get(t.vehicle_class, (0, 255, 0))
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        label = f"{t.vehicle_class} {t.track_id.split('-')[-1]}"
        speed = getattr(t, "_speed_label", None)
        if speed:
            label += f" | {speed}"
        cv2.rectangle(out, (x1, y1 - 18), (x1 + 8 * len(label), y1), color, -1)
        cv2.putText(out, label, (x1 + 2, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
        # trajectory
        pts = [(int(px), int(py)) for _, _, px, py in list(t.trajectory)[-20:]]
        for i in range(1, len(pts)):
            cv2.line(out, pts[i - 1], pts[i], color, 1)

    banner = f"{camera_name}  |  ENV:{environment.upper()}  |  {backend.upper()}"
    cv2.rectangle(out, (0, 0), (w, 22), (20, 20, 20), -1)
    cv2.putText(out, banner, (6, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 230, 255), 1, cv2.LINE_AA)
    return out


def encode_jpeg(frame: np.ndarray, quality: int = 70) -> bytes:
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return buf.tobytes() if ok else b""
