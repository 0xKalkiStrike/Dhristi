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
        await ws.send_json({"type": "connected", "message": "DRISHTI-V live stream connected"})
        while True:
            # client may send pings/filters; we simply keep the socket alive
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception as exc:  # pragma: no cover
        logger.warning("ws error: %s", exc)
        manager.disconnect(ws)
