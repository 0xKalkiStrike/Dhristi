"""DRISHTI-V FastAPI application entrypoint."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import api_router
from app.core.config import settings
from app.core.exceptions import (
    DrishtiError, drishti_exception_handler, unhandled_exception_handler,
)
from app.core.logging_config import configure_logging, get_logger
from app.database.session import init_db
from app.database.mongo import mongo
from app.services.pipeline import pipeline_manager
from app.websocket.manager import manager
from app.websocket.routes import router as ws_router

configure_logging("DEBUG" if settings.debug else "INFO")
logger = get_logger("drishti.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting %s v%s", settings.app_name, settings.version)
    settings.ensure_dirs()
    init_db()
    manager.set_loop(asyncio.get_running_loop())
    await mongo.connect()  # optional live-event store; degrades gracefully if down
    logger.info("DRISHTI-V ready", extra={"extra_fields": {
        "detector": settings.detector_backend, "ocr": settings.ocr_engine,
        "db": "sqlite" if settings.database_url.startswith("sqlite") else "postgres",
        "mongo": mongo.connected}})
    yield
    logger.info("shutting down; stopping pipelines")
    pipeline_manager.stop_all()
    await mongo.close()


app = FastAPI(
    title=settings.app_name,
    description=settings.app_subtitle,
    version=settings.version,
    lifespan=lifespan,
)

# Allow configured origins, plus any private-LAN origin when enabled so other
# devices on the same network can use the app.
_lan_regex = (
    r"^http://(localhost|127\.0\.0\.1|(10|192\.168|172\.(1[6-9]|2\d|3[01]))\.[0-9.]+)(:\d+)?$"
    if settings.cors_allow_lan else None
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=_lan_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(DrishtiError, drishti_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(api_router)
app.include_router(ws_router)

# serve saved plate crops / frames for the UI
try:
    app.mount("/data", StaticFiles(directory=str(settings.data_dir)), name="data")
except Exception:  # pragma: no cover
    pass


_INFO = {
    "name": settings.app_name,
    "subtitle": settings.app_subtitle,
    "version": settings.version,
    "docs": "/docs",
    "health": "/api/system/health",
    "websocket": "/ws/events",
}


@app.get("/api", include_in_schema=False)
def api_info() -> dict:
    return _INFO


# ---- Single-port app serving ----
# If the frontend has been built, serve it from the backend so the whole app
# (UI + API + WebSocket) is reachable on ONE port — ideal for phones/other
# devices on the LAN (only port 8000 needs to be open). Falls back to JSON info.
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from app.core.config import REPO_ROOT  # noqa: E402

_DIST = REPO_ROOT / "frontend" / "dist"
_RESERVED = ("api", "ws", "data", "docs", "openapi", "redoc")

if (_DIST / "index.html").exists():
    _assets = _DIST / "assets"
    if _assets.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="spa-assets")

    @app.get("/", include_in_schema=False)
    async def spa_root():
        return FileResponse(str(_DIST / "index.html"))

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        if full_path.split("/", 1)[0] in _RESERVED:
            return JSONResponse({"error": "not_found"}, status_code=404)
        candidate = _DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(_DIST / "index.html"))  # SPA deep-link fallback
else:
    @app.get("/", include_in_schema=False)
    def root() -> dict:
        return _INFO
