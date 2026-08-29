"""Domain exceptions and FastAPI exception handlers."""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.logging_config import get_logger

logger = get_logger("drishti.errors")


class DrishtiError(Exception):
    """Base class for expected, handled application errors."""

    status_code = 400
    code = "drishti_error"

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code


class NotFoundError(DrishtiError):
    status_code = 404
    code = "not_found"


class CalibrationError(DrishtiError):
    status_code = 422
    code = "calibration_error"


class ValidationError(DrishtiError):
    status_code = 422
    code = "validation_error"


class VideoSourceError(DrishtiError):
    status_code = 400
    code = "video_source_error"


async def drishti_exception_handler(request: Request, exc: DrishtiError):
    logger.warning("handled error: %s", exc.message, extra={"extra_fields": {"code": exc.code, "path": request.url.path}})
    return JSONResponse(status_code=exc.status_code, content={"error": exc.code, "detail": exc.message})


async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled error: %s", exc, exc_info=True, extra={"extra_fields": {"path": request.url.path}})
    return JSONResponse(status_code=500, content={"error": "internal_error", "detail": "An internal error occurred."})
