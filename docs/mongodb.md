# MongoDB (native, non-Docker)

DRISHTI-V uses MongoDB as a complementary **live-event / analytics store**. Every real-time
event broadcast over the WebSocket (`speed_event`, `traffic_event`, `plate_detected`,
`vehicle_updated`, `camera_status`) is mirrored into a MongoDB collection, giving a flexible,
index-friendly document log for fast querying and aggregation. The SQL database remains the
primary source of truth; **MongoDB is optional and the platform degrades gracefully** if it is
not running.

## Why not Docker?
Per requirement, MongoDB runs **natively**. The setup script uses the **portable Community
Server ZIP** — no installer, no administrator rights, no containers — and runs `mongod` from a
local folder against a local `--dbpath`.

## Setup & run
```powershell
# Download (if needed) + start MongoDB on 127.0.0.1:27017
scripts\setup\setup_mongodb.ps1

# Or download/extract only, then start later:
scripts\setup\setup_mongodb.ps1 -InstallOnly
scripts\setup\run_mongodb.ps1
```
The script:
1. Reuses an existing `mongod` (PATH / `C:\Program Files\MongoDB`) if present.
2. Otherwise downloads the portable ZIP into `data/mongodb/dist` and extracts it.
3. Starts `mongod --dbpath data/mongodb/db --port 27017 --bind_ip 127.0.0.1`.

Data lives under `data/mongodb/db` (git-ignored). Alternative installs:
```powershell
winget install -e --id MongoDB.Server --accept-package-agreements --accept-source-agreements
```

## Configuration (`backend/.env`)
```
MONGODB_ENABLED=true
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB=drishti_v
MONGODB_EVENTS_COLLECTION=live_events
MONGODB_TIMEOUT_MS=1500
```
Set `MONGODB_ENABLED=false` to disable it entirely.

## How it connects
On startup the FastAPI app calls `mongo.connect()` (async **Motor** driver) with a short
server-selection timeout. If MongoDB is unreachable it logs a warning and continues; the SQL
pipeline is unaffected. `GET /api/system/health` reports `mongo_enabled` / `mongo_connected`.

## Endpoints
| Endpoint | Purpose |
|---|---|
| `GET /api/mongo/status` | connection state + event counts by type |
| `GET /api/mongo/events?event_type=&camera_id=&limit=` | recent mirrored events |
| `GET /api/mongo/analytics` | event counts aggregated by type (`$group`) |

Indexes are created on `type`, `camera_id`, `ts`, and `(type, ts)` for fast queries.

## Verify
```bash
curl http://localhost:8000/api/mongo/status
# after running the demo:
curl "http://localhost:8000/api/mongo/events?event_type=speed_event&limit=5"
```
Or from `mongosh` (bundled in the portable ZIP under `data/mongodb/dist/*/bin`):
```
use drishti_v
db.live_events.countDocuments({})
db.live_events.find({type:"traffic_event"}).sort({ts:-1}).limit(5)
```

## Tests
`backend/tests/test_mongo.py` verifies record/query/aggregate against an in-memory Mongo mock
(`mongomock-motor`), so the integration is tested even without a running server.
