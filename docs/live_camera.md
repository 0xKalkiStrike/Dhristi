# Live Camera Connection (no demo data)

Connect a **real** camera so the pipeline runs on live frames with the real detector
(YOLO), instead of the bundled demo scenes. Three sources are supported from
**Camera Management → Connect Live Camera**:

| Source | Use it for | How |
|---|---|---|
| **Webcam** | Built-in / USB camera | Scan → pick the device → Connect & Start |
| **Bluetooth** | A Bluetooth camera paired in the OS | Scan → connect by device index |
| **Phone / IP** | A phone or IP camera over Wi-Fi | Paste its RTSP/HTTP stream URL |

Connected live cameras use `demo_detector=None` → the **auto detector (YOLO)** on real frames.

## Webcam
The backend enumerates OS camera devices (`GET /api/devices/video`) and you connect by
index. On Windows the capture opens with **Media Foundation** (falls back to DirectShow),
which can take a few seconds to warm up on first open — this is normal.
```bash
curl -X POST http://localhost:8000/api/devices/connect \
  -H "Content-Type: application/json" \
  -d '{"name":"Front Gate","source_type":"webcam","index":0,"start":true}'
```

## Bluetooth camera — how it really works
**Bluetooth (BLE/Classic) cannot stream real-time video by itself** — the bandwidth is far
too low. The supported, honest path is:

1. **Pair the Bluetooth camera in the OS** (Windows Settings → Bluetooth & devices).
2. Once paired, a Bluetooth *camera* is exposed by the OS as a **normal video device** and
   appears in `GET /api/devices/video` (often with "Bluetooth" in the name).
3. Connect it by its device index — the app opens it exactly like a webcam.

`GET /api/devices/bluetooth` lists paired Bluetooth devices (via Windows PnP) to help you
identify the camera; the UI clearly states the pairing requirement. If your "Bluetooth
camera" is really a Wi-Fi camera that pairs over BLE for setup, use the **Phone / IP** option
with its RTSP/HTTP URL instead.

## Phone as a camera (recommended for a quick live demo)
Install an IP-webcam app on a phone on the same Wi-Fi, then paste its stream URL:
```
rtsp://192.168.1.9:8080/h264      # RTSP
http://192.168.1.9:8080/video     # MJPEG/HTTP
```
```bash
curl -X POST http://localhost:8000/api/devices/connect \
  -H "Content-Type: application/json" \
  -d '{"name":"Phone Cam","source_type":"rtsp","url":"rtsp://192.168.1.9:8080/h264","start":true}'
```

## Endpoints
| Endpoint | Purpose |
|---|---|
| `GET /api/devices/video` | OS camera devices + suggested indices |
| `GET /api/devices/bluetooth` | paired Bluetooth devices (+ guidance) |
| `GET /api/devices/probe?index=N` | open device N briefly and report resolution |
| `POST /api/devices/connect` | create + start a live camera (webcam/bluetooth/rtsp) |

## Notes
- Detection only fires on relevant objects (vehicles, and person). Point the camera at
  traffic/people to see boxes; an empty scene correctly shows **0 detections** (not faked).
- Live cameras run YOLO when available; the tile banner shows the active detector.
- A camera in use by another app cannot be opened — close other apps first.
