"""WebSocket route for real-time events."""
from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logging_config import get_logger
from app.websocket.manager import manager

logger = get_logger("drishti.ws")
router = APIRouter()


@router.websocket("/ws/events")
async def events_ws(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            # client may send pings/filters; keep connection open
            await ws.receive_text()
    except (WebSocketDisconnect, RuntimeError):
        pass
    except Exception as exc:  # pragma: no cover
        logger.debug("ws closed: %s", exc)
    finally:
        manager.disconnect(ws)


@router.websocket("/ws/devices/ingest/{camera_id}")
@router.websocket("/ws/ingest/{camera_id}")
async def camera_ingest_ws(ws: WebSocket, camera_id: str):
    """High-speed persistent WebSocket ingestion for mobile/phone camera streams."""
    import cv2
    import numpy as np
    from app.video.push import push_frame
    from app.services.pipeline import pipeline_manager

    await ws.accept()
    logger.info("phone camera websocket connected for %s", camera_id)
    try:
        while True:
            data = await ws.receive_bytes()
            if not data:
                continue
            arr = np.frombuffer(data, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is not None:
                p = pipeline_manager.get(camera_id)
                if p and p.is_alive():
                    push_frame(camera_id, img)
    except (WebSocketDisconnect, RuntimeError):
        pass
    except Exception as exc:
        logger.debug("camera ingest ws closed for %s: %s", camera_id, exc)
    finally:
        logger.info("phone camera websocket disconnected for %s", camera_id)

