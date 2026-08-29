# DRISHTI-V

**Dynamic Road Intelligence & Surveillance Through Intelligent Vision**

An intelligent, multi-camera video-analytics platform built for the *Unified Viewing and Selective Analysis* problem statement (Gujarat Police hackathon). DRISHTI-V ingests multiple video sources, detects and tracks vehicles, estimates **calibrated** speed, performs **ANPR/OCR**, searches vehicles across cameras, builds cross-camera journeys, detects traffic events, and adapts to fog / night / rain — all with **confidence scores and a human-verification workflow**.

> Real AI/CV pipeline. No fabricated results. Where a capability needs calibration or suitable input, the UI says so instead of inventing numbers.

---

## 1. Overview

| Capability | Status |
|---|---|
| Unified multi-camera viewing (live annotated tiles) | ✅ |
| Vehicle detection (YOLOv8 / torchvision / classical fallback) | ✅ |
| Multi-object tracking (ByteTrack-style) | ✅ |
| Calibrated speed estimation (dual-line + homography) | ✅ |
| ANPR / number-plate OCR (EasyOCR / Tesseract / PaddleOCR) | ✅ |
| Vehicle search & selective analysis | ✅ |
| Cross-camera vehicle journey (probabilistic association) | ✅ |
| Environment adaptation (fog/night/low-light enhancement) | ✅ |
| Rule-based, explainable traffic events | ✅ |
| Real-time dashboard + WebSocket live events | ✅ |
| Explainable speed results, confidence, audit logs | ✅ |
| MongoDB live-event store (native, non-Docker) | ✅ |
| FastAPI HTTP+WebSocket port-forwarder | ✅ |
| Live camera connect (webcam / Bluetooth / phone-IP) | ✅ |
| LAN access from other devices | ✅ |

## 2. Architecture

```
Video (file / RTSP / webcam)
  → Frame sampling
  → Environment analysis (ImageQualityService)
  → Adaptive enhancement (fog/night/…)  [original always retained]
  → Detection (YOLO / torchvision / motion)
  → Tracking (ByteTrack) → trajectories
  → Speed estimation (calibrated)
  → ANPR (plate detect → OCR → normalise → validate)
  → Vehicle identity + cross-camera association
  → Event detection (overspeed, wrong-way, stopped, dwell, restricted, congestion)
  → Database (SQLAlchemy) → WebSocket → React command-center dashboard
```

Each camera runs in its **own worker thread** with its own DB session, so one failing
camera never stops the platform. Heavy models are shared and warmed up once.

```
backend/app
  core/            config, logging, exceptions
  database/        engine + session (SQLite default, PostgreSQL supported)
  models/          SQLAlchemy tables
  schemas/         Pydantic DTOs
  ai/
    detection/     base + yolo + torchvision + motion + factory
    tracking/      ByteTrack-style tracker
    speed/         formulas + calibration + estimator
    anpr/          plate_detector + ocr/{easyocr,tesseract,paddle} + pipeline + normalizer
    enhancement/   enhancers + adaptive pipeline
    environment/   image-quality classifier
    reidentification/ appearance signature + similarity
  events/          rule-based detectors
  video/           VideoSource abstraction
  services/        pipeline orchestrator, identity, search, demo
  websocket/       connection manager + routes
  api/routers/     cameras, calibration, vehicles, detections, analysis, demo, system
frontend/src       React + TS + Vite + Tailwind command center
```

## 3. Requirements

- **Python 3.11+** (tested on 3.13)
- **Node 18+** (tested on Node 22)
- ~2 GB free disk for models
- GPU optional — the app auto-detects CUDA and falls back to CPU with lower FPS

## 4. Quick start (local)

### Backend
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    |  Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python ../scripts/setup/init_db.py
python ../scripts/setup/download_models.py     # YOLO weights + OCR check
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Backend: http://localhost:8000 · API docs: http://localhost:8000/docs

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Dashboard: http://localhost:5173  (dev server proxies `/api` and `/ws` to `:8000`)

### One-Click All-in-One Launch (Single Terminal + Port Forwarding)
```cmd
run.bat
```
Starts the full stack in **one terminal** and displays all URLs: Localhost, LAN (Wi-Fi), Swagger Docs, and a **Public Port-Forwarding Tunnel URL**!

### Windows PowerShell one-liners
```powershell
scripts\setup\setup_backend.ps1
scripts\setup\run_backend.ps1        # in one terminal
scripts\setup\setup_frontend.ps1
scripts\setup\run_frontend.ps1       # in another terminal
```

## 5. Demo mode (one click)

1. Start backend + frontend.
2. Open the dashboard and press **▶ START DEMO** (top bar), or:
   ```bash
   curl -X POST http://localhost:8000/api/demo/start
   ```
This generates bundled synthetic multi-camera scenes (`data/sample_videos/`) and runs
the full pipeline live: detection → tracking → **calibrated speed** → **real OCR of
rendered plates** → overspeed events → cross-camera journeys.

> **Honesty note.** Demo scenes are synthetic *input* — vehicles genuinely move and carry
> real rendered plates. The pipeline runs **real CV** on them (classical motion detection,
> since abstract blobs are not COCO objects; the UI labels the active detector). OCR really
> reads the plate pixels; speed is really computed from calibration. Drop a real traffic
> `.mp4` into `data/sample_videos/` (or upload via the UI) and YOLO takes over automatically.

The recommended demo path: START DEMO → watch grid + live events → search a plate
(e.g. `GJ01AB1234`) → open the vehicle → view cross-camera journey → open a speed event →
read the explainable calculation → note the foggy/night cameras still processing with
confidence indicators.

## 6. Environment variables

See [`backend/.env.example`](backend/.env.example). Key ones:

| Var | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/drishti.db` | SQLite by default; set a `postgresql+psycopg://…` DSN for PostgreSQL |
| `DETECTOR_BACKEND` | `auto` | `auto`\|`yolo`\|`torchvision`\|`motion`\|`null` |
| `AI_DEVICE` | `auto` | `auto`\|`cpu`\|`cuda` |
| `OCR_ENGINE` | `easyocr` | `easyocr`\|`tesseract`\|`paddleocr` |
| `PROCESS_FPS` | `12` | target processing FPS (CPU-friendly) |
| `DETECT_EVERY_N_FRAMES` | `3` | run the deep detector every N frames |
| `DEFAULT_SPEED_LIMIT_KMH` | `60` | fallback speed limit |
| `MAX_UPLOAD_MB` | `500` | video upload cap |

Never commit real RTSP credentials — configure them via a camera's `source_uri` at runtime.

## 7. Speed estimation methodology

Speed is **never** derived from raw pixel displacement. Two calibrated methods:

- **Dual virtual lines** a known real-world distance apart. Speed = distance ÷ time-between-crossings.
- **Homography** (perspective transform, 4 image ↔ 4 world points) → metric displacement over time.

`speed_kmh = (metres / seconds) × 3.6`. Zero/negative time and missing calibration are guarded
(never divide by zero). Results are labelled **Estimated** and carry a confidence score; without
calibration the UI shows *“Speed estimation unavailable — camera calibration required.”*
See [docs/speed_calibration.md](docs/speed_calibration.md).

## 8. ANPR methodology

Vehicle crop → classical plate-region detection (edge density + aspect ratio) → OCR-oriented
preprocessing → OCR (pluggable engine) → **position-aware** Indian-plate normalisation → format
validation → combined confidence. Raw and normalised text are both stored; low-confidence or
invalid-format reads are flagged **Needs Verification**. See [docs/anpr.md](docs/anpr.md).

## 9. Testing

```bash
cd backend
python -m pytest -q
```
Covers speed math & unit conversion, calibration, tracking & detection parsing, OCR
normalisation & plate validation, event detection, environment classification, and API
integration (health, camera CRUD, calibration validation, search, demo setup).

End-to-end pipeline check (no server needed):
```bash
python backend/scripts/demo/verify_pipeline.py
```

## 10. Docker

```bash
cd docker
docker compose up --build
```
Starts PostgreSQL, backend and frontend. AI inference runs on CPU inside the container by
default; for GPU, run the backend natively (see [docs/installation.md](docs/installation.md)).

## 11. RTSP

Add a camera with `source_type=rtsp` and `source_uri=rtsp://user:pass@host:554/stream`
(kept private, never logged raw). The platform is fully functional in file mode when RTSP
is unavailable — that is the default hackathon demo path.

## 11a. MongoDB (native, non-Docker live-event store)

MongoDB mirrors every real-time event into a queryable document collection alongside SQL.
It runs **natively** (portable Community ZIP — no Docker, no admin) and is **optional**
(the app degrades gracefully if it is down).
```powershell
scripts\setup\setup_mongodb.ps1        # download (if needed) + start on 127.0.0.1:27017
```
```bash
curl http://localhost:8000/api/mongo/status
curl "http://localhost:8000/api/mongo/events?event_type=speed_event&limit=5"
```
Config: `MONGODB_ENABLED`, `MONGODB_URL`, `MONGODB_DB`. Full guide: [docs/mongodb.md](docs/mongodb.md).

## 11b. Port forwarding (FastAPI reverse proxy)

`scripts/port_forward.py` is a FastAPI app that forwards **HTTP + WebSocket** from a listen
port to the backend, exposing API + live `/ws/events` behind one port (LAN / NAT / single
entrypoint).
```powershell
scripts\setup\run_port_forward.ps1     # 0.0.0.0:9000 -> http://127.0.0.1:8000
```
```bash
python scripts/port_forward.py --listen-port 9000 --target http://127.0.0.1:8000
curl http://localhost:9000/api/system/health          # forwarded to the backend
```
Full guide: [docs/port_forwarding.md](docs/port_forwarding.md).

## 11c. Live camera (no demo data)

Connect a **real** camera and run live analysis (YOLO) instead of demo scenes — from
**Camera Management → Connect Live Camera**: **Webcam**, **Bluetooth** (OS-paired camera),
or **Phone/IP** (RTSP/HTTP stream). Detection only fires on real objects (0 detections on an
empty scene — never faked). Bluetooth cannot carry video itself; a Bluetooth camera must be
paired in the OS, after which it appears as a normal video device. Full guide:
[docs/live_camera.md](docs/live_camera.md).
```bash
curl -X POST http://localhost:8000/api/devices/connect \
  -H "Content-Type: application/json" \
  -d '{"name":"Front Gate","source_type":"webcam","index":0,"start":true}'
```

## 11d. Access from other devices (LAN)

```powershell
scripts\setup\run_network.ps1        # backend + frontend on 0.0.0.0, prints the phone URL
```
Open `http://<LAN-IP>:5173` on any device on the same Wi-Fi. `GET /api/system/network` returns
the URLs; CORS allows private-LAN origins (`CORS_ALLOW_LAN=true`). If a device can't connect,
run `scripts\setup\open_firewall.ps1` (admin). Full guide: [docs/network_access.md](docs/network_access.md).

## 12. Troubleshooting

| Symptom | Fix |
|---|---|
| `CUDA not available` | Expected on CPU machines — the app runs on CPU automatically. |
| Camera tile shows *NO SIGNAL* | Start the pipeline (▶ on the camera / demo) or check `source_uri`. |
| OCR returns nothing | EasyOCR downloads models on first use (~64 MB); ensure network on first run, or switch `OCR_ENGINE`. |
| YOLO not used | Install `ultralytics`; otherwise torchvision/motion fallback is used (labelled in UI). |
| Port in use | Change `--port` / Vite `server.port`. |

## 13. Limitations

Speed accuracy depends on calibration and camera perspective; severe fog/blur reduces
detection and OCR accuracy; cross-camera identity is **probabilistic**; AI outputs require
human verification for enforcement. Full list: [docs/limitations.md](docs/limitations.md).

## 14. Future improvements

Deep plate-detection & re-ID models, learned low-light enhancement, GIS map overlay,
authorised database integration, edge/GPU deployment, additional camera protocols. Clean
interfaces (`VehicleDetector`, `OCRProvider`, `VehicleTracker`, …) make these drop-in.

---

*Built as a working hackathon MVP. Confidence-aware, gracefully degrading, and honest about
what it can and cannot measure.*
"# Dhristi" 
