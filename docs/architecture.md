# Architecture

## Processing pipeline (per camera)

```
VideoSource.read()                      # file / rtsp / webcam, source-relative timestamps
  → frame sampling (step = src_fps / PROCESS_FPS)
  → ImageQualityService.analyze()       # brightness, contrast, blur, fog, low-light → environment
  → AdaptiveEnhancer.enhance()          # dehaze / gamma / CLAHE / denoise (original retained)
  → VehicleDetector.detect()            # YOLO | torchvision | motion (deep models sampled)
      ↳ if enhanced frame yields higher mean confidence, keep it (never assumed better)
  → ByteTracker.update()                # 2-stage IoU + linear motion, occlusion tolerant
  → SpeedEstimator.update() per track   # dual-line crossing or homography displacement
  → ANPRPipeline.read_plate()           # gated on plate visibility; classical detect + OCR
  → VehicleIdentityService              # create/associate identity, cross-camera journey
  → EventEngine                         # overspeed, wrong-way, stopped, dwell, restricted, congestion
  → DB persist + WebSocket broadcast + annotated JPEG for the live tile
```

## Concurrency model

- `PipelineManager` owns one `CameraPipeline` per camera; each runs in a **daemon thread**
  with its **own SQLAlchemy session**. A crash in one thread is caught, logged, sets the
  camera to `error`, and never affects other cameras.
- Heavy models (YOLO, ANPR/OCR) are **shared singletons**, lazily built and warmed once.
- Worker threads publish events to the asyncio event loop via
  `ConnectionManager.broadcast_threadsafe` (`run_coroutine_threadsafe`).

## Abstractions (extension points)

| Interface | Implementations |
|---|---|
| `VehicleDetector` | `YOLODetector`, `TorchvisionDetector`, `MotionDetector`, `_NullDetector` |
| `VehicleTracker` | `ByteTracker` |
| `OCRProvider` | `EasyOCRProvider`, `TesseractProvider`, `PaddleOCRProvider` |
| `Calibration` | `dual_line`, `homography` |
| Enhancers | dehaze, gamma, CLAHE, denoise, sharpen, white-balance |

Factories (`build_detector`, `build_ocr_provider`) select the best **available** backend and
degrade gracefully, so the platform runs whether or not GPU/heavy models are present.

## Data flow to the UI

- REST (`/api/*`) for CRUD, search, analytics, calibration.
- WebSocket (`/ws/events`) for `vehicle_detected`, `vehicle_updated`, `plate_detected`,
  `speed_event`, `traffic_event`, `camera_status`.
- MJPEG-style live tiles via `/api/cameras/{id}/frame.jpg` (latest annotated frame).
