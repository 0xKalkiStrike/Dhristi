"""MongoDB integration tests.

Uses an in-memory Mongo mock (mongomock-motor) so the store logic is verified
without a running MongoDB server. When a real server is running, the same code
path is exercised end-to-end. Dependency-free (no pytest-asyncio needed).
"""
import asyncio

from app.core.config import settings
from app.database.mongo import MongoManager


def _mock_manager():
    from mongomock_motor import AsyncMongoMockClient
    m = MongoManager()
    client = AsyncMongoMockClient()
    m._db = client[settings.mongodb_db]
    m._connected = True
    return m, client


def test_record_and_query_events():
    async def run():
        m, client = _mock_manager()
        try:
            await m.record_event({"type": "speed_event", "camera_id": "CAM-001", "speed_kmh": 96, "is_violation": True})
            await m.record_event({"type": "plate_detected", "camera_id": "CAM-002", "plate": "GJ01AB1234"})
            await m.record_event({"type": "speed_event", "camera_id": "CAM-001", "speed_kmh": 40})

            all_events = await m.recent_events(limit=10)
            assert len(all_events) == 3
            assert all("ts" in e for e in all_events)
            assert all("_id" not in e for e in all_events)

            assert len(await m.recent_events(event_type="speed_event")) == 2
            assert len(await m.recent_events(camera_id="CAM-001")) == 2
        finally:
            client.close()

    asyncio.run(run())


def test_aggregate_counts_and_stats():
    async def run():
        m, client = _mock_manager()
        try:
            for _ in range(3):
                await m.record_event({"type": "traffic_event", "camera_id": "CAM-003"})
            await m.record_event({"type": "speed_event", "camera_id": "CAM-003"})

            counts = await m.aggregate_event_counts()
            assert counts.get("traffic_event") == 3
            assert counts.get("speed_event") == 1

            stats = await m.stats()
            assert stats["connected"] is True
            assert stats["event_count"] == 4
        finally:
            client.close()

    asyncio.run(run())


def test_disconnected_manager_is_safe():
    async def run():
        m = MongoManager()
        assert m.connected is False
        await m.record_event({"type": "x"})       # no-op, must not raise
        assert await m.recent_events() == []
        assert await m.aggregate_event_counts() == {}

    asyncio.run(run())
