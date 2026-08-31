"""End-to-end pipeline verification (no web server needed).

Generates the demo scenes, runs the real pipeline on CAM-001 for a few seconds,
then reports what the CV/AI stack actually produced. Uses an isolated DB.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(line_buffering=True, encoding="utf-8")
except Exception:
    pass

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))
os.environ["DATABASE_URL"] = f"sqlite:///{(BACKEND / 'data' / 'verify_drishti.db').as_posix()}"
os.environ["DETECTOR_BACKEND"] = "motion"

# fresh db
for ext in ("", "-wal", "-shm"):
    p = Path(str(BACKEND / "data" / "verify_drishti.db") + ext)
    if p.exists():
        p.unlink()

from app.database.session import SessionLocal, init_db          # noqa: E402
from app.models import (Detection, PlateRead, SpeedEvent, Track,  # noqa: E402
                        TrafficEvent, Vehicle, VehicleJourney)
from app.services.demo import setup_demo                          # noqa: E402
from app.services.pipeline import pipeline_manager               # noqa: E402
from sqlalchemy import func, select                              # noqa: E402

RUN_SECONDS = int(os.environ.get("VERIFY_SECONDS", "22"))


def main() -> int:
    init_db()
    db = SessionLocal()
    dataset = setup_demo(db)
    db.commit()
    print(f"[setup] {len(dataset)} demo cameras + calibrations ready", flush=True)
    expected = {v["plate"]: v["target_speed_kmh"] for c in dataset for v in c["expected"]}

    from app.models import Camera
    cam = db.scalar(select(Camera).where(Camera.camera_id == "CAM-001"))
    print(f"[start] running pipeline on {cam.camera_id} ({cam.name}) for {RUN_SECONDS}s ...", flush=True)
    p = pipeline_manager.start(cam, loop=True, demo_detector="motion")

    t0 = time.time()
    while time.time() - t0 < RUN_SECONDS:
        time.sleep(3)
        print(f"  [stats] frames={p.stats['frames']} dets={p.stats['detections']} "
              f"tracks={p.stats['tracks']} plates={p.stats['plates']} "
              f"speed_events={p.stats['speed_events']} events={p.stats['traffic_events']} "
              f"env={p.stats['environment']} fps={p.stats['fps']}", flush=True)
    pipeline_manager.stop("CAM-001")
    time.sleep(2)

    def count(model):
        return db.scalar(select(func.count()).select_from(model)) or 0

    print("\n===== RESULTS (DB persisted) =====")
    print(f"detections     : {count(Detection)}")
    print(f"tracks         : {count(Track)}")
    print(f"speed_events   : {count(SpeedEvent)}")
    print(f"plate_reads    : {count(PlateRead)}")
    print(f"traffic_events : {count(TrafficEvent)}")
    print(f"vehicles       : {count(Vehicle)}")
    print(f"journeys       : {count(VehicleJourney)}")

    print("\n--- speed events ---")
    for se in db.scalars(select(SpeedEvent).order_by(SpeedEvent.speed_kmh.desc())).all():
        print(f"  {se.plate_number or se.tracking_id}: {se.speed_kmh:.1f} km/h "
              f"(limit {se.speed_limit_kmh:.0f}, {'VIOLATION' if se.is_violation else 'ok'}, "
              f"conf {se.confidence:.2f}, {se.method})")

    print("\n--- plate reads (real OCR) ---")
    for pr in db.scalars(select(PlateRead).order_by(PlateRead.confidence.desc())).all():
        flag = "NEEDS VERIFICATION" if pr.needs_verification else "OK"
        print(f"  raw='{pr.raw_text}' -> '{pr.normalized_text}' conf={pr.confidence:.2f} "
              f"valid={pr.valid_format} [{flag}] via {pr.ocr_engine}")

    print("\n--- traffic events ---")
    for te in db.scalars(select(TrafficEvent).order_by(TrafficEvent.timestamp)).all():
        print(f"  [{te.severity}] {te.event_type}: {te.reason}")

    print(f"\n[expected demo speeds] {expected}")
    ok = count(Detection) > 0 and count(Track) > 0 and count(SpeedEvent) > 0
    print("\nRESULT:", "PASS [OK]" if ok else "PARTIAL [WARN]")
    db.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
