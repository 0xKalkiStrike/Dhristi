"""System health & runtime info."""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db
from app.database.mongo import mongo
from app.schemas import HealthOut
from app.services.pipeline import get_shared_detector, pipeline_manager
from app.ai.detection.factory import resolve_device
from app.websocket.manager import manager

router = APIRouter(prefix="/api/system", tags=["system"])
_START = time.time()


def _cuda_available() -> bool:
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:
        return False


@router.get("/health", response_model=HealthOut)
def health(db: Session = Depends(get_db)) -> HealthOut:
    db_ok = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover
        db_ok = f"error: {exc}"
    device = resolve_device(settings.ai_device)
    return HealthOut(
        status="ok",
        version=settings.version,
        ai_runtime="GPU" if device == "cuda" else "CPU",
        detector_backend=settings.detector_backend,
        ocr_engine=settings.ocr_engine,
        device=device,
        database=db_ok,
        mongo_enabled=mongo.enabled,
        mongo_connected=mongo.connected,
        cuda_available=_cuda_available(),
        active_pipelines=pipeline_manager.active_count,
        uptime_seconds=round(time.time() - _START, 1),
    )


@router.get("/runtime")
def runtime() -> dict:
    device = resolve_device(settings.ai_device)
    detector = get_shared_detector()
    info = {
        "device": device,
        "ai_runtime": "GPU" if device == "cuda" else "CPU",
        "detector": detector.info(),
        "cuda_available": _cuda_available(),
        "ws_clients": manager.client_count,
        "config": {
            "process_fps": settings.process_fps,
            "detect_every_n_frames": settings.detect_every_n_frames,
            "detection_confidence": settings.detection_confidence,
            "ocr_engine": settings.ocr_engine,
            "enhancement_enabled": settings.enhancement_enabled,
        },
    }
    try:
        import psutil  # optional
        info["cpu_percent"] = psutil.cpu_percent()
        info["memory_percent"] = psutil.virtual_memory().percent
    except Exception:
        pass
    return info


@router.get("/pipelines")
def pipelines() -> dict:
    return {"active": pipeline_manager.active_count, "pipelines": pipeline_manager.all_status()}


@router.get("/network")
def network() -> dict:
    """LAN addresses + ready-to-share URLs for accessing the app from other devices."""
    import socket
    primary = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))          # no packets sent; just resolves the route
        primary = s.getsockname()[0]
        s.close()
    except Exception:
        pass
    ips: list[str] = []
    try:
        _, _, addrs = socket.gethostbyname_ex(socket.gethostname())
        ips = [a for a in addrs if not a.startswith("127.")]
    except Exception:
        pass
    if primary and primary not in ips:
        ips.insert(0, primary)
    ips = [a for a in ips if not a.startswith("169.254.")] or ips
    host = primary or (ips[0] if ips else "localhost")
    from app.core.config import REPO_ROOT
    served = (REPO_ROOT / "frontend" / "dist" / "index.html").exists()
    app_url = f"http://{host}:{settings.port}" if served else f"http://{host}:5173"
    return {
        "hostname": socket.gethostname(),
        "primary_ip": primary,
        "lan_ips": ips,
        "frontend_bundled": served,
        "urls": {
            # single-port app URL to share with other devices (recommended)
            "app": app_url,
            "frontend_dev": f"http://{host}:5173",
            "backend": f"http://{host}:{settings.port}",
            "port_forwarder": f"http://{host}:9000",
            "api_docs": f"http://{host}:{settings.port}/docs",
        },
        "hint": (f"Open {app_url} on any device on the same Wi-Fi. If it says "
                 "'address unreachable', allow the port through Windows Firewall "
                 "(run scripts/setup/open_firewall.ps1 as admin) or set the Wi-Fi to a Private network."),
    }
