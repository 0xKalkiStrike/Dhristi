# Port Forwarding (FastAPI reverse proxy)

`scripts/port_forward.py` is a small **FastAPI + Uvicorn** application that forwards **HTTP and
WebSocket** traffic from a listen port to the DRISHTI-V backend (or any target). It lets you
expose the whole platform — REST API **and** the live `/ws/events` stream — behind a single
port/interface, e.g. for LAN access, a router/NAT port-forward, or a single public entrypoint.

## Run
```powershell
# 0.0.0.0:9000  ->  http://127.0.0.1:8000   (HTTP + WebSocket)
scripts\setup\run_port_forward.ps1

# custom
scripts\setup\run_port_forward.ps1 -ListenHost 0.0.0.0 -ListenPort 8080 -Target http://127.0.0.1:8000
```
```bash
# cross-platform
python scripts/port_forward.py --listen-host 0.0.0.0 --listen-port 9000 --target http://127.0.0.1:8000
# or as an ASGI app (env: TARGET_URL)
TARGET_URL=http://127.0.0.1:8000 uvicorn scripts.port_forward:app --host 0.0.0.0 --port 9000
```

Environment overrides: `LISTEN_HOST`, `LISTEN_PORT`, `TARGET_URL`.

## What it does
- **HTTP** — a catch-all route (`/{path:path}`, all methods) streams the request body to the
  upstream via `httpx` and streams the response back, preserving status and headers. Hop-by-hop
  headers (`connection`, `transfer-encoding`, `upgrade`, …) are stripped per RFC 7230.
- **WebSocket** — `/{path:path}` accepts the client socket, opens an upstream connection with the
  `websockets` client, and relays frames **bidirectionally** (text + binary) until either side
  closes. Query strings are preserved (so `/ws/events?token=…` works).
- **Bad gateway** — if the upstream is unreachable, returns HTTP 502 with a JSON detail.
- `GET /__forwarder__/health` — reports the forwarder status and whether the upstream is up.

## Verify
```bash
curl http://localhost:9000/__forwarder__/health          # {"forwarder":"ok","upstream":"up"}
curl http://localhost:9000/api/system/health             # forwarded to the backend
# WebSocket:
python - <<'PY'
import asyncio, websockets
async def m():
    async with websockets.connect("ws://127.0.0.1:9000/ws/events") as ws:
        print(await ws.recv())
asyncio.run(m())
PY
```

## Notes
- Point the frontend at the forwarded port with `VITE_API_BASE` / `VITE_WS_BASE`, or simply
  browse the API through it.
- This is a development/LAN convenience proxy. For public production exposure, terminate TLS at a
  hardened reverse proxy (nginx/Caddy/Traefik) and add auth.
