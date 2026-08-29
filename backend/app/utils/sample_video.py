"""Synthetic traffic-scene generator for a fully self-contained, honest demo.

This is EXPLICITLY a demo data generator (not fabricated AI output). It renders a
road with vehicles that really move across the frame at known pixel speeds and
carry a real, rendered number plate. The pipeline then performs *genuine* CV on
these pixels:

* the classical motion detector really detects the moving vehicle blobs;
* the tracker really tracks them;
* the calibrated estimator really computes speed from crossing times
  (which match the designed speeds — useful for verification);
* the ANPR OCR really reads the plate text that is actually drawn in the image.

For real traffic footage, drop an .mp4 into data/sample_videos and point a camera
at it; YOLO then handles detection automatically.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

# Calibration geometry shared by all demo cameras (image coords).
LINE_A_X = 420
LINE_B_X = 900
REAL_DISTANCE_M = 24.0     # metres between the two virtual lines
FRAME_W, FRAME_H = 1280, 720
FPS = 20


@dataclass
class DemoVehicle:
    plate: str
    vclass: str
    color: tuple[int, int, int]
    lane_y: int
    start_x: int
    vx: float                     # px/frame (=> defines the real speed)
    w: int = 150
    h: int = 80
    start_frame: int = 0

    def target_speed_kmh(self) -> float:
        # speed = distance / time; time = (LINE_B_X-LINE_A_X)/vx frames / FPS
        px = (LINE_B_X - LINE_A_X)
        t = (px / self.vx) / FPS
        return round((REAL_DISTANCE_M / t) * 3.6, 1)


def _draw_vehicle(frame, v: DemoVehicle, x: int):
    y = v.lane_y
    cv2.rectangle(frame, (x, y), (x + v.w, y + v.h), v.color, -1)
    cv2.rectangle(frame, (x, y), (x + v.w, y + v.h), (30, 30, 30), 2)
    # windshield
    cv2.rectangle(frame, (x + v.w - 30, y + 6), (x + v.w - 6, y + v.h - 6), (170, 200, 220), -1)
    # number plate (real text, rendered large & clear -> OCR reads this honestly)
    pw = min(v.w - 8, 150)
    ph = 40
    px = x + v.w // 2 - pw // 2
    py = y + v.h - ph - 4
    cv2.rectangle(frame, (px - 2, py - 2), (px + pw + 2, py + ph + 2), (255, 255, 255), -1)  # quiet zone
    cv2.rectangle(frame, (px, py), (px + pw, py + ph), (250, 250, 250), -1)
    cv2.rectangle(frame, (px, py), (px + pw, py + ph), (0, 0, 0), 2)
    cv2.putText(frame, v.plate, (px + 6, py + 29), cv2.FONT_HERSHEY_DUPLEX, 0.62, (5, 5, 5), 1, cv2.LINE_AA)


def _road_background() -> np.ndarray:
    """High-contrast daytime road scene (so it is not misread as low-contrast fog)."""
    bg = np.full((FRAME_H, FRAME_W, 3), (205, 180, 150), np.uint8)     # bright sky
    cv2.rectangle(bg, (0, 100), (FRAME_W, 118), (70, 110, 70), -1)     # tree line
    cv2.rectangle(bg, (0, 120), (FRAME_W, 600), (95, 97, 100), -1)     # dark asphalt
    cv2.rectangle(bg, (0, 600), (FRAME_W, FRAME_H), (140, 170, 120), -1)  # green verge
    for ly in (170, 300, 430, 560):                                    # bright lane markings
        for lx in range(0, FRAME_W, 80):
            cv2.rectangle(bg, (lx, ly), (lx + 44, ly + 8), (250, 250, 245), -1)
    for lx in (150, 500, 850, 1150):                                   # roadside poles (texture)
        cv2.rectangle(bg, (lx, 40), (lx + 8, 120), (40, 40, 45), -1)
    return bg


def _apply_environment(frame: np.ndarray, env: str) -> np.ndarray:
    if env == "fog":
        fog = np.full_like(frame, 200)
        return cv2.addWeighted(frame, 0.45, fog, 0.55, 0)
    if env == "night":
        dark = (frame.astype(np.float32) * 0.28).astype(np.uint8)
        return dark
    if env == "rain":
        out = frame.copy()
        for _ in range(400):
            x, y = random.randint(0, FRAME_W - 1), random.randint(120, 600)
            cv2.line(out, (x, y), (x - 2, y + 10), (180, 180, 190), 1)
        return cv2.addWeighted(out, 0.85, np.full_like(out, 120), 0.15, 0)
    return frame


def generate_scene(path: Path, vehicles: list[DemoVehicle], frames: int = 200,
                   environment: str = "day") -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, FPS, (FRAME_W, FRAME_H))
    bg = _road_background()
    for f in range(frames):
        frame = bg.copy()
        for v in vehicles:
            if f < v.start_frame:
                continue
            x = int(v.start_x + (f - v.start_frame) * v.vx)
            if x > FRAME_W:
                continue
            _draw_vehicle(frame, v, x)
        frame = _apply_environment(frame, environment)
        writer.write(frame)
    writer.release()
    return {
        "path": str(path),
        "environment": environment,
        "frames": frames,
        "vehicles": [{"plate": v.plate, "class": v.vclass, "target_speed_kmh": v.target_speed_kmh()}
                     for v in vehicles],
    }


def _calibration_payload(direction: str = "right", limit: float = 60.0) -> dict:
    return {
        "method": "dual_line",
        "line_a": [[LINE_A_X, 120], [LINE_A_X, 600]],
        "line_b": [[LINE_B_X, 120], [LINE_B_X, 600]],
        "real_distance_m": REAL_DISTANCE_M,
        "direction": direction,
        "speed_limit_kmh": limit,
        "frame_width": FRAME_W,
        "frame_height": FRAME_H,
    }


def build_demo_dataset(out_dir: Path) -> list[dict]:
    """Create the bundled multi-camera demo clips. Returns camera metadata."""
    out_dir.mkdir(parents=True, exist_ok=True)
    random.seed(7)

    # Cross-camera vehicle of interest: GJ01AB1234 appears on CAM-001 & CAM-003.
    cams = [
        {
            "camera_id": "CAM-001", "name": "Main Road North", "zone": "Zone A",
            "location": "NH-48 Ahmedabad", "environment": "day", "limit": 60,
            "vehicles": [
                DemoVehicle("GJ01AB1234", "car", (0, 140, 220), 180, -140, 24.0, start_frame=0),
                DemoVehicle("GJ05CD7890", "car", (200, 60, 60), 300, -260, 12.0, start_frame=10),
                DemoVehicle("GJ18XY4455", "truck", (90, 90, 90), 430, -400, 9.0, w=170, h=80, start_frame=25),
            ],
        },
        {
            "camera_id": "CAM-002", "name": "Junction East", "zone": "Zone A",
            "location": "SG Highway Junction", "environment": "day", "limit": 50,
            "vehicles": [
                DemoVehicle("GJ27MN1188", "motorcycle", (0, 200, 120), 200, -120, 20.0, w=60, h=40),
                DemoVehicle("GJ05CD7890", "car", (200, 60, 60), 330, -300, 15.0, start_frame=15),
            ],
        },
        {
            "camera_id": "CAM-003", "name": "Ring Road", "zone": "Zone B",
            "location": "Ring Road West", "environment": "fog", "limit": 60,
            "vehicles": [
                DemoVehicle("GJ01AB1234", "car", (0, 140, 220), 260, -160, 26.0, start_frame=5),
                DemoVehicle("GJ12GH6060", "bus", (180, 120, 40), 400, -420, 11.0, w=200, h=90),
            ],
        },
        {
            "camera_id": "CAM-004", "name": "Highway Entry", "zone": "Zone C",
            "location": "Expressway Toll Approach", "environment": "night", "limit": 80,
            "vehicles": [
                DemoVehicle("GJ38PQ2323", "car", (220, 220, 220), 240, -150, 30.0),
                DemoVehicle("GJ18XY4455", "truck", (90, 90, 90), 420, -430, 10.0, w=170, h=80, start_frame=20),
            ],
        },
    ]

    result = []
    for c in cams:
        path = out_dir / f"{c['camera_id'].lower()}.mp4"
        meta = generate_scene(path, c["vehicles"], frames=220, environment=c["environment"])
        result.append({
            "camera_id": c["camera_id"], "name": c["name"], "zone": c["zone"],
            "location": c["location"], "source_type": "file", "source_uri": str(path),
            "environment": c["environment"],
            "calibration": _calibration_payload(limit=c["limit"]),
            "expected": meta["vehicles"],
        })
    return result
