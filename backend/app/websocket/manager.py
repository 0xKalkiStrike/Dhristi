"""WebSocket connection manager & thread-safe event bus.

Pipeline workers run in background threads; they publish events through
``broadcast_threadsafe`` which hops onto the main asyncio loop safely.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
from collections import deque
from typing import Any

from fastapi import WebSocket

from app.core.logging_config import get_logger

logger = get_logger("drishti.ws")


class ConnectionManager:
    def __init__(self, history: int = 100):
        self._connections: set[WebSocket] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._recent: deque[dict] = deque(maxlen=history)

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.add(ws)
        # replay recent events so a newly connected client is not blank
        for evt in list(self._recent)[-25:]:
            try:
                await ws.send_text(json.dumps(evt, default=str))
            except Exception:
                break
        logger.info("ws client connected", extra={"extra_fields": {"clients": len(self._connections)}})

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard(ws)

    async def broadcast(self, event: dict[str, Any]) -> None:
        if "timestamp" not in event:
            event["timestamp"] = dt.datetime.now(dt.timezone.utc).isoformat()
        self._recent.append(event)
        # Mirror the event into MongoDB (best-effort; never blocks the broadcast).
        try:
            from app.database.mongo import mongo
            if mongo.connected:
                await mongo.record_event(event)
        except Exception:  # pragma: no cover
            pass
        dead = []
        payload = json.dumps(event, default=str)
        for ws in list(self._connections):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    def broadcast_threadsafe(self, event: dict[str, Any]) -> None:
        """Callable from worker threads."""
        if self._loop is None:
            self._recent.append(event)
            return
        try:
            asyncio.run_coroutine_threadsafe(self.broadcast(event), self._loop)
        except Exception as exc:  # pragma: no cover
            logger.warning("threadsafe broadcast failed: %s", exc)

    @property
    def client_count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()
