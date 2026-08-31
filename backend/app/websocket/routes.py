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
