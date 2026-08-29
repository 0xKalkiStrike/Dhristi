"""Structured logging for DRISHTI-V.

Emits key=value structured records to stdout. Secrets are never logged; a small
redaction helper masks known-sensitive keys defensively.
"""
from __future__ import annotations

import logging
import sys
from typing import Any

_SENSITIVE = {"password", "passwd", "secret", "token", "rtsp_url", "authorization", "api_key"}


def redact(data: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for k, v in data.items():
        if any(s in k.lower() for s in _SENSITIVE):
            out[k] = "***"
        else:
            out[k] = v
    return out


class KeyValueFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = f"{self.formatTime(record, '%Y-%m-%dT%H:%M:%S')} " \
               f"level={record.levelname} logger={record.name} msg={record.getMessage()!r}"
        extra = getattr(record, "extra_fields", None)
        if extra:
            kv = " ".join(f"{k}={v}" for k, v in redact(extra).items())
            base = f"{base} {kv}"
        if record.exc_info:
            base = f"{base}\n{self.formatException(record.exc_info)}"
        return base


_configured = False


def configure_logging(level: str = "INFO") -> None:
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(KeyValueFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    # Quiet noisy libraries
    for noisy in ("uvicorn.access", "matplotlib", "PIL", "ultralytics"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_kv(logger: logging.Logger, level: int, msg: str, **fields: Any) -> None:
    logger.log(level, msg, extra={"extra_fields": fields})
