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
    scale_factor = max(0.5, min(1.5, w / 640.0))

    # calibration lines with anti-aliasing
    if calibration is not None and getattr(calibration, "method", "") == "dual_line" and calibration.line_a:
        for line, col in ((calibration.line_a, (0, 255, 255)), (calibration.line_b, (0, 165, 255))):
            if line and len(line) == 2:
                pt1 = (int(round(line[0][0])), int(round(line[0][1])))
                pt2 = (int(round(line[1][0])), int(round(line[1][1])))
                cv2.line(out, pt1, pt2, col, max(1, int(round(2 * scale_factor))), cv2.LINE_AA)

    for t in tracks:
        x1, y1, x2, y2 = (int(round(v)) for v in t.bbox)
        # Ensure bounding box is within frame bounds
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w - 1, x2), min(h - 1, y2)
        if x2 <= x1 or y2 <= y1:
            continue

        color = _CLASS_COLORS.get(t.vehicle_class, (0, 255, 0))
        thickness = max(1, int(round(2 * scale_factor)))
        
        # Smooth bounding box with corner highlights
        cv2.rectangle(out, (x1, y1), (x2, y2), color, thickness, cv2.LINE_AA)
        
        # Corner accent notches for modern HUD look
        c_len = max(4, min(18, (x2 - x1) // 5, (y2 - y1) // 5))
        # Top-left
        cv2.line(out, (x1, y1), (x1 + c_len, y1), (255, 255, 255), thickness, cv2.LINE_AA)
        cv2.line(out, (x1, y1), (x1, y1 + c_len), (255, 255, 255), thickness, cv2.LINE_AA)
        # Top-right
        cv2.line(out, (x2, y1), (x2 - c_len, y1), (255, 255, 255), thickness, cv2.LINE_AA)
        cv2.line(out, (x2, y1), (x2, y1 + c_len), (255, 255, 255), thickness, cv2.LINE_AA)
        # Bottom-left
        cv2.line(out, (x1, y2), (x1 + c_len, y2), (255, 255, 255), thickness, cv2.LINE_AA)
        cv2.line(out, (x1, y2), (x1, y2 - c_len), (255, 255, 255), thickness, cv2.LINE_AA)
        # Bottom-right
        cv2.line(out, (x2, y2), (x2 - c_len, y2), (255, 255, 255), thickness, cv2.LINE_AA)
        cv2.line(out, (x2, y2), (x2, y2 - c_len), (255, 255, 255), thickness, cv2.LINE_AA)

        label = f"{t.vehicle_class.upper()} {t.track_id.split('-')[-1]}"
        speed = getattr(t, "_speed_label", None)
        if speed:
            label += f" | {speed}"
        
        f_scale = max(0.32, min(0.5, 0.38 * scale_factor))
        badge_h = int(round(16 * scale_factor))
        badge_w = int(round((7.5 * len(label) + 8) * scale_factor))
        badge_y = max(badge_h, y1)
        cv2.rectangle(out, (x1, badge_y - badge_h), (min(w, x1 + badge_w), badge_y), color, -1)
        cv2.putText(out, label, (x1 + int(4 * scale_factor), badge_y - int(4 * scale_factor)),
                    cv2.FONT_HERSHEY_SIMPLEX, f_scale, (0, 0, 0), 1, cv2.LINE_AA)

        # Smooth continuous trajectory trail (Gaussian sub-pixel curve smoothing)
        raw_pts = [(float(px), float(py)) for _, _, px, py in list(t.trajectory)[-25:]]
        n_raw = len(raw_pts)
        if n_raw > 1:
            smooth_pts = []
            for i in range(n_raw):
                if i == 0 or i == n_raw - 1:
                    smooth_pts.append(raw_pts[i])
                else:
                    sx = 0.25 * raw_pts[i - 1][0] + 0.5 * raw_pts[i][0] + 0.25 * raw_pts[i + 1][0]
                    sy = 0.25 * raw_pts[i - 1][1] + 0.5 * raw_pts[i][1] + 0.25 * raw_pts[i + 1][1]
                    smooth_pts.append((sx, sy))
            
            n_pts = len(smooth_pts)
            for i in range(1, n_pts):
                pt1 = (int(round(smooth_pts[i - 1][0])), int(round(smooth_pts[i - 1][1])))
                pt2 = (int(round(smooth_pts[i][0])), int(round(smooth_pts[i][1])))
                t_thick = max(1, int(round(2 * scale_factor))) if i > n_pts - 6 else 1
                cv2.line(out, pt1, pt2, color, t_thick, cv2.LINE_AA)

    banner_h = int(round(22 * scale_factor))
    banner = f"{camera_name}  |  ENV: {environment.upper()}  |  {backend.upper()}"
    cv2.rectangle(out, (0, 0), (w, banner_h), (20, 20, 20), -1)
    banner_fscale = max(0.30, min(0.48, 0.40 * scale_factor))
    cv2.putText(out, banner, (int(8 * scale_factor), int(round(banner_h * 0.7))),
                cv2.FONT_HERSHEY_SIMPLEX, banner_fscale, (0, 230, 255), 1, cv2.LINE_AA)
    return out


def encode_jpeg(frame: np.ndarray, quality: int = 75) -> bytes:
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return buf.tobytes() if ok else b""
