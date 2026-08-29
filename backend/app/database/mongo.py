"""MongoDB integration (async, via Motor).

MongoDB is used as a complementary **live event / analytics store** alongside the
primary SQL database: every real-time event broadcast over the WebSocket is also
mirrored into a MongoDB collection, giving a flexible, index-friendly log that is
easy to query and aggregate.

The connection is optional and fails **gracefully** — if MongoDB is not running
the rest of the platform is unaffected (SQL remains the source of truth). Start a
native MongoDB with ``scripts/setup/setup_mongodb.ps1`` (no Docker required).
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger("drishti.mongo")


class MongoManager:
    """Lazily-connected Motor client with graceful degradation."""

    def __init__(self) -> None:
        self._client = None
        self._db = None
        self._connected = False
        self._last_error: Optional[str] = None

    @property
    def enabled(self) -> bool:
        return settings.mongodb_enabled

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    @property
    def db(self):
        return self._db

    async def connect(self) -> bool:
        """Attempt to connect. Never raises; returns True on success."""
        if not self.enabled:
            logger.info("MongoDB disabled via config")
            return False
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
        except Exception as exc:  # pragma: no cover
            self._last_error = f"motor not installed: {exc}"
            logger.warning(self._last_error)
            return False
        try:
            self._client = AsyncIOMotorClient(
                settings.mongodb_url,
                serverSelectionTimeoutMS=settings.mongodb_timeout_ms,
                uuidRepresentation="standard",
            )
            await self._client.admin.command("ping")
            self._db = self._client[settings.mongodb_db]
            await self._ensure_indexes()
            self._connected = True
            self._last_error = None
            logger.info("MongoDB connected", extra={"extra_fields": {
                "db": settings.mongodb_db, "url": settings.mongodb_url.split("@")[-1]}})
            return True
        except Exception as exc:
            self._connected = False
            self._last_error = str(exc)
            logger.warning("MongoDB unavailable (continuing without it): %s", exc)
            return False

    async def _ensure_indexes(self) -> None:
        col = self._db[settings.mongodb_events_collection]
        await col.create_index("type")
        await col.create_index("camera_id")
        await col.create_index("ts")
        await col.create_index([("type", 1), ("ts", -1)])

    async def record_event(self, event: dict[str, Any]) -> None:
        """Persist one live event. Best-effort; swallows errors."""
        if not self._connected or self._db is None:
            return
        try:
            doc = dict(event)
            doc["ts"] = dt.datetime.now(dt.timezone.utc)
            await self._db[settings.mongodb_events_collection].insert_one(doc)
        except Exception as exc:  # pragma: no cover
            logger.debug("mongo record_event failed: %s", exc)

    async def recent_events(self, *, event_type: str | None = None, camera_id: str | None = None,
                            limit: int = 100) -> list[dict]:
        if not self._connected or self._db is None:
            return []
        query: dict[str, Any] = {}
        if event_type:
            query["type"] = event_type
        if camera_id:
            query["camera_id"] = camera_id
        cursor = self._db[settings.mongodb_events_collection].find(query, {"_id": 0}).sort("ts", -1).limit(limit)
        return [self._clean(d) async for d in cursor]

    async def aggregate_event_counts(self) -> dict[str, int]:
        if not self._connected or self._db is None:
            return {}
        pipeline = [{"$group": {"_id": "$type", "count": {"$sum": 1}}}]
        out: dict[str, int] = {}
        async for row in self._db[settings.mongodb_events_collection].aggregate(pipeline):
            out[row["_id"] or "unknown"] = row["count"]
        return out

    async def stats(self) -> dict:
        info = {"enabled": self.enabled, "connected": self._connected,
                "url": settings.mongodb_url.split("@")[-1], "db": settings.mongodb_db,
                "error": self._last_error}
        if self._connected and self._db is not None:
            try:
                info["event_count"] = await self._db[settings.mongodb_events_collection].count_documents({})
                info["counts_by_type"] = await self.aggregate_event_counts()
            except Exception as exc:  # pragma: no cover
                info["error"] = str(exc)
        return info

    @staticmethod
    def _clean(doc: dict) -> dict:
        ts = doc.get("ts")
        if isinstance(ts, dt.datetime):
            doc["ts"] = ts.isoformat()
        return doc

    async def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._connected = False


mongo = MongoManager()
