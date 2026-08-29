# API Reference

Interactive OpenAPI docs are served at **`/docs`** (Swagger) and **`/redoc`**.

## System
- `GET  /api/system/health` — status, AI runtime (GPU/CPU), detector, OCR, DB, uptime.
- `GET  /api/system/runtime` — device, detector info, config, CPU/mem (if psutil).
- `GET  /api/system/pipelines` — per-camera live processing stats.

## Cameras
- `GET  /api/cameras` · `POST /api/cameras` · `GET/PATCH/DELETE /api/cameras/{id}`
- `POST /api/cameras/{id}/start?loop=&detector=` · `POST /api/cameras/{id}/stop`
- `GET  /api/cameras/{id}/status`
- `GET  /api/cameras/{id}/frame.jpg` — latest annotated live frame.

## Calibration
- `GET  /api/calibration/{camera_id}`
- `POST /api/calibration/{camera_id}` — save dual_line / homography calibration.
- `GET  /api/calibration/{camera_id}/frame.jpg?index=` — frame for calibration.
- `POST /api/calibration/{camera_id}/test` — validate geometry (synthetic or supplied track).

## Vehicles & selective analysis
- `GET  /api/vehicles?limit=`
- `GET  /api/vehicles/search?plate=&vehicle_type=&color=&camera_id=&min_speed=&max_speed=&event_type=&min_confidence=&direction=`
- `GET  /api/vehicles/{uid}` — vehicle + observations + journey + speed events + plate reads.
- `GET  /api/vehicles/{uid}/journey` — cross-camera journey.

## Detections / events / analytics
- `GET  /api/detections` · `GET /api/tracks` · `GET /api/plate-reads`
- `GET  /api/speed-events` · `GET /api/speed-events/{id}` (explainable payload in `details`)
- `GET  /api/traffic-events` · `GET /api/alerts` · `GET /api/audit-logs`
- `GET  /api/analytics/summary?hours=`

## Analysis & upload
- `POST /api/video/upload` (multipart) — validates type/size, optionally creates a camera.
- `POST /api/analysis/start` · `POST /api/analysis/stop` · `GET /api/analysis/status`

## Demo
- `POST /api/demo/setup` · `POST /api/demo/start` · `POST /api/demo/stop`

## WebSocket
- `WS /ws/events` — JSON messages: `vehicle_detected`, `vehicle_updated`, `plate_detected`,
  `speed_event`, `traffic_event`, `camera_status`. Recent events are replayed on connect.

### Example: search a plate
```bash
curl "http://localhost:8000/api/vehicles/search?plate=GJ01AB1234"
```
```json
{ "count": 4, "results": [
  { "plate_number": "GJ01AB1234", "camera_id": "CAM-001", "speed_kmh": 86.4,
    "vehicle_class": "car", "detection_confidence": 0.94, "timestamp": "…" }
]}
```
