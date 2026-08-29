"""MongoDB-backed live-event store endpoints.

MongoDB mirrors every real-time event (speed, ANPR, traffic, camera status) into
a flexible document collection for fast querying/aggregation. These endpoints are
independent of the SQL store and return empty/disconnected states gracefully.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.database.mongo import mongo

router = APIRouter(prefix="/api/mongo", tags=["mongodb"])


@router.get("/status")
async def mongo_status() -> dict:
    return await mongo.stats()


@router.get("/events")
async def mongo_events(
    event_type: str | None = Query(None, description="filter by event type"),
    camera_id: str | None = Query(None),
    limit: int = Query(100, le=1000),
) -> dict:
    if not mongo.connected:
        return {"connected": False, "count": 0, "events": [],
                "hint": "Start MongoDB with scripts/setup/setup_mongodb.ps1"}
    events = await mongo.recent_events(event_type=event_type, camera_id=camera_id, limit=limit)
    return {"connected": True, "count": len(events), "events": events}


@router.get("/analytics")
async def mongo_analytics() -> dict:
    if not mongo.connected:
        return {"connected": False, "counts_by_type": {}}
    return {"connected": True, "counts_by_type": await mongo.aggregate_event_counts()}
