"""DRISHTI-V — FastAPI port-forwarder / reverse proxy.

Forwards **HTTP and WebSocket** traffic from a listen port to a target service
(default: the DRISHTI-V backend on 127.0.0.1:8000). Use it to expose the backend
on another interface/port — e.g. bind 0.0.0.0:9000 for LAN access or router
port-forwarding, presenting API + live `/ws/events` behind a single entrypoint.

Examples
--------
    # expose backend (127.0.0.1:8000) on all interfaces, port 9000
    python scripts/port_forward.py --listen-port 9000 --target http://127.0.0.1:8000

    # forward to a different host
    python scripts/port_forward.py --listen-host 0.0.0.0 --listen-port 8080 \
        --target http://192.168.1.50:8000

Environment overrides: LISTEN_HOST, LISTEN_PORT, TARGET_URL.
"""
from __future__ import annotations

import argparse
import asyncio
import os
from urllib.parse import urlparse

import httpx
import uvicorn
import websockets
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse

# Hop-by-hop headers must not be forwarded (RFC 7230 §6.1).
HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
}


def build_app(target_url: str) -> FastAPI:
    target = target_url.rstrip("/")
    parsed = urlparse(target)
    target_host = parsed.hostname or "127.0.0.1"
    target_port = parsed.port or (443 if parsed.scheme == "https" else 80)
    ws_scheme = "wss" if parsed.scheme == "https" else "ws"
    ws_base = f"{ws_scheme}://{target_host}:{target_port}"

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await client.aclose()

    app = FastAPI(title="DRISHTI-V Port Forwarder", description=f"Reverse proxy → {target}", lifespan=lifespan)
    client = httpx.AsyncClient(timeout=httpx.Timeout(60.0, read=None), follow_redirects=False)

    @app.get("/__forwarder__/health")
    async def forwarder_health() -> JSONResponse:
        upstream = "unknown"
        try:
            r = await client.get(f"{target}/api/system/health", timeout=3)
            upstream = "up" if r.status_code == 200 else f"http {r.status_code}"
        except Exception as exc:
            upstream = f"down: {exc}"
        return JSONResponse({"forwarder": "ok", "target": target, "upstream": upstream})

    # ---------------- WebSocket proxy ----------------
    @app.websocket("/{path:path}")
    async def ws_proxy(client_ws: WebSocket, path: str) -> None:
        await client_ws.accept()
        qs = client_ws.url.query
        upstream_uri = f"{ws_base}/{path}" + (f"?{qs}" if qs else "")
        try:
            async with websockets.connect(upstream_uri, max_size=None) as upstream:
                await _pump_websocket(client_ws, upstream)
        except Exception:
            try:
                await client_ws.close()
            except Exception:
                pass

    # ---------------- HTTP proxy (catch-all) ----------------
    @app.api_route("/{path:path}",
                   methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
    async def http_proxy(request: Request, path: str) -> StreamingResponse:
        url = f"{target}/{path}"
        headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP_BY_HOP}
        headers["host"] = f"{target_host}:{target_port}"

        req = client.build_request(
            request.method, url, headers=headers,
            params=request.query_params, content=request.stream(),
        )
        try:
            upstream = await client.send(req, stream=True)
        except httpx.ConnectError as exc:
            return JSONResponse(status_code=502,
                                content={"error": "bad_gateway", "detail": f"upstream unreachable: {exc}"})

        resp_headers = {k: v for k, v in upstream.headers.items() if k.lower() not in HOP_BY_HOP}

        async def body_iter():
            try:
                async for chunk in upstream.aiter_raw():
                    yield chunk
            finally:
                await upstream.aclose()

        return StreamingResponse(body_iter(), status_code=upstream.status_code, headers=resp_headers)

    return app


async def _pump_websocket(client_ws: WebSocket, upstream) -> None:
    """Bidirectionally relay frames between the client and the upstream socket."""

    async def client_to_upstream() -> None:
        try:
            while True:
                msg = await client_ws.receive()
                if msg["type"] == "websocket.disconnect":
                    break
                if msg.get("text") is not None:
                    await upstream.send(msg["text"])
                elif msg.get("bytes") is not None:
                    await upstream.send(msg["bytes"])
        except WebSocketDisconnect:
            pass
        finally:
            await upstream.close()

    async def upstream_to_client() -> None:
        try:
            async for message in upstream:
                if isinstance(message, (bytes, bytearray)):
                    await client_ws.send_bytes(message)
                else:
                    await client_ws.send_text(message)
        except Exception:
            pass
        finally:
            try:
                await client_ws.close()
            except Exception:
                pass

    await asyncio.gather(client_to_upstream(), upstream_to_client(), return_exceptions=True)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="FastAPI HTTP+WebSocket port forwarder")
    p.add_argument("--listen-host", default=os.getenv("LISTEN_HOST", "0.0.0.0"))
    p.add_argument("--listen-port", type=int, default=int(os.getenv("LISTEN_PORT", "9000")))
    p.add_argument("--target", default=os.getenv("TARGET_URL", "http://127.0.0.1:8000"),
                   help="upstream base URL (default http://127.0.0.1:8000)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    app = build_app(args.target)
    print(f"[port-forward] {args.listen_host}:{args.listen_port}  ->  {args.target}  (HTTP + WebSocket)")
    uvicorn.run(app, host=args.listen_host, port=args.listen_port, log_level="info")


# Importable ASGI app using env defaults (e.g. `uvicorn scripts.port_forward:app`)
app = build_app(os.getenv("TARGET_URL", "http://127.0.0.1:8000"))


if __name__ == "__main__":
    main()
