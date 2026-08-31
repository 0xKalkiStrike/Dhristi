"""WebSocket connection manager & thread-safe event bus.

Pipeline workers run in background threads; they publish events through
``broadcast_threadsafe`` which safely pushes to asynchronous per-client queues.
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
        self._clients: dict[WebSocket, asyncio.Queue[str]] = {}
        self._tasks: dict[WebSocket, asyncio.Task] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._recent: deque[dict] = deque(maxlen=history)

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=100)
        self._clients[ws] = queue

        # Replay recent events so a newly connected client is not blank
        for evt in list(self._recent)[-25:]:
            try:
                queue.put_nowait(json.dumps(evt, default=str))
            except Exception:
                break

        # Start dedicated non-blocking writer task for this WebSocket
        task = asyncio.create_task(self._writer(ws, queue))
        self._tasks[ws] = task
        logger.info("ws client connected", extra={"extra_fields": {"clients": len(self._clients)}})

    async def _writer(self, ws: WebSocket, queue: asyncio.Queue[str]) -> None:
        """Dedicated coroutine per client to avoid concurrent send_text race conditions."""
        try:
            while True:
                msg = await queue.get()
                await ws.send_text(msg)
                queue.task_done()
        except Exception:
            pass
        finally:
            self.disconnect(ws)

    def disconnect(self, ws: WebSocket) -> None:
        queue = self._clients.pop(ws, None)
        task = self._tasks.pop(ws, None)
        if task and not task.done():
            task.cancel()
        try:
            if queue:
                while not queue.empty():
                    queue.get_nowait()
                    queue.task_done()
        except Exception:
            pass

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

        payload = json.dumps(event, default=str)
        dead = []
        for ws, queue in list(self._clients.items()):
            try:
                if queue.full():
                    try:
                        queue.get_nowait()  # Drop oldest message to prevent lag on slow clients
                        queue.task_done()
                    except Exception:
                        pass
                queue.put_nowait(payload)
            except Exception:
                dead.append(ws)

        for ws in dead:
            self.disconnect(ws)

    def broadcast_threadsafe(self, event: dict[str, Any]) -> None:
        """Callable from background worker threads."""
        if self._loop is None or self._loop.is_closed():
            self._recent.append(event)
            return
        try:
            asyncio.run_coroutine_threadsafe(self.broadcast(event), self._loop)
        except Exception as exc:  # pragma: no cover
            logger.warning("threadsafe broadcast failed: %s", exc)

    @property
    def client_count(self) -> int:
        return len(self._clients)


manager = ConnectionManager()
