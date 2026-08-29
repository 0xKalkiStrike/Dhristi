# Demo Guide

## One-click
Open the dashboard → **▶ START DEMO** (top bar). Or:
```bash
curl -X POST http://localhost:8000/api/demo/start
```

This regenerates bundled synthetic scenes and starts the pipeline on four cameras:

| Camera | Name | Zone | Environment | Speed limit |
|---|---|---|---|---|
| CAM-001 | Main Road North | Zone A | day | 60 |
| CAM-002 | Junction East | Zone A | day | 50 |
| CAM-003 | Ring Road | Zone B | **fog** | 60 |
| CAM-004 | Highway Entry | Zone C | **night** | 80 |

The vehicle **`GJ01AB1234`** appears on CAM-001 and CAM-003 to demonstrate cross-camera
journey and search.

## Recommended demo path
1. **Unified View** — four live tiles with detection boxes, track IDs, trajectories, the two
   calibration lines, and per-tile environment (day/fog/night). Live event feed on the right.
2. A vehicle crosses the calibrated zone → **speed** appears; overspeed → red **OVERSPEED**
   event with an explanation.
3. **Selective Analysis** → search `GJ01AB1234` → observations across cameras.
4. Click a result → **Vehicle detail**: cross-camera **journey timeline**, plate reads, and
   speed events.
5. Click a speed event → **Explainable Speed Result** (distance, elapsed, method, confidence).
6. Note CAM-003 (fog) and CAM-004 (night): adaptive enhancement engages; confidence indicators
   remain visible.

## Honesty of the demo
Synthetic scenes are **input only**. The pipeline runs genuine CV:
- **Motion detector** (real background-subtraction CV) finds the moving vehicles — the demo
  uses it because abstract blobs are not COCO objects; the tile banner shows the active detector.
- **OCR really reads** the plate text drawn in the frame (not fabricated).
- **Speed** is really computed from the calibrated geometry — measured values match the designed
  speeds (e.g. CAM-001 `GJ01AB1234` ≈ 86 km/h against a 60 limit → violation).

For real footage, drop an `.mp4` into `data/sample_videos/` or use **Camera Management →
Upload Video**; YOLO is selected automatically for real scenes.

## Regenerate scenes manually
```bash
python backend/scripts/demo/generate_sample_video.py
```
