"""Local capture-device & Bluetooth enumeration.

Discovers OS video devices (webcams and any Bluetooth camera the OS exposes) and
paired Bluetooth devices, so an operator can connect a **live** camera instead of
using demo footage. Uses Windows PnP via PowerShell (no extra Python deps).

Honest note on Bluetooth: BLE/Bluetooth Classic cannot stream real-time video on
its own. A Bluetooth *camera* must be paired in the OS first; the OS then presents
it as a normal video device, which we open by index like a webcam.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading

from app.core.logging_config import get_logger

logger = get_logger("drishti.devices")

_IS_WIN = sys.platform.startswith("win")


def _powershell(command: str, timeout: int = 6) -> str:
    if not _IS_WIN:
        return ""
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=timeout,
        )
        return proc.stdout or ""
    except Exception as exc:  # pragma: no cover
        logger.warning("powershell query failed: %s", exc)
        return ""


def _parse_json_list(raw: str) -> list[dict]:
    raw = (raw or "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    if isinstance(data, dict):
        return [data]
    return data if isinstance(data, list) else []


def list_video_devices() -> dict:
    """OS camera devices with suggested OpenCV indices (order = index)."""
    devices = []
    if _IS_WIN:
        raw = _powershell(
            "Get-PnpDevice -Class Camera -Status OK | "
            "Select-Object FriendlyName,Status | ConvertTo-Json -Compress",
            timeout=5,
        )
        rows = _parse_json_list(raw)
        for i, r in enumerate(rows):
            name = r.get("FriendlyName") or f"Camera {i}"
            devices.append({"index": i, "name": name, "status": r.get("Status", "OK"),
                            "is_bluetooth": "blue" in name.lower()})

    # Always ensure at least default indices 0 and 1 are available as options
    if not devices:
        devices = [
            {"index": 0, "name": "Integrated / USB Webcam (Index 0)", "status": "OK", "is_bluetooth": False},
            {"index": 1, "name": "Secondary Camera (Index 1)", "status": "OK", "is_bluetooth": False},
        ]
    return {"count": len(devices), "devices": devices, "platform": sys.platform}


def list_bluetooth_devices() -> dict:
    """Paired/known Bluetooth devices. Cameras among these can be selected."""
    raw = _powershell(
        "Get-PnpDevice -Class Bluetooth -Status OK | "
        "Select-Object FriendlyName,Status | ConvertTo-Json -Compress",
        timeout=5,
    )
    rows = _parse_json_list(raw)
    devices = []
    for r in rows:
        name = r.get("FriendlyName") or "Bluetooth device"
        low = name.lower()
        devices.append({
            "name": name, "status": r.get("Status", "OK"),
            "looks_like_camera": any(k in low for k in ("cam", "camera", "video", "webcam")),
            "is_adapter": "adapter" in low or "radio" in low,
        })
    return {
        "count": len(devices),
        "devices": devices,
        "platform": sys.platform,
        "note": ("Bluetooth cannot stream live video directly. Pair a Bluetooth camera in "
                 "the OS; once it appears as a camera device it can be opened by index "
                 "(see /api/devices/video)."),
    }


def probe_video_index(index: int, timeout: float = 2.0) -> dict:
    """Try to open a local video device by index and grab one frame (bounded)."""
    result: dict = {"index": index, "ok": False, "error": None, "width": 0, "height": 0}
    if index < 0 or index > 10:
        result["error"] = f"device index {index} out of valid range (0-10)"
        return result

    def _work():
        cap = None
        try:
            from app.video.sources import _open_local_camera
            cap = _open_local_camera(index)
            if cap is None or not cap.isOpened():
                result["error"] = "device did not open"
                return
            ok, frame = cap.read()
            if ok and frame is not None:
                result["ok"] = True
                result["height"], result["width"] = frame.shape[:2]
            else:
                result["error"] = "opened but no frame"
        except Exception as exc:  # pragma: no cover
            result["error"] = str(exc)
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass

    t = threading.Thread(target=_work, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        result["error"] = f"probe timed out ({timeout}s) - device in use or permission denied"
    return result
