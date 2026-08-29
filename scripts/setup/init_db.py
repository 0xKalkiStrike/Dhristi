"""Initialise the database schema (idempotent)."""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))

from app.database.session import init_db  # noqa: E402
from app.core.config import settings      # noqa: E402


def main() -> int:
    print(f"Initialising database: {settings.database_url}")
    init_db()
    print("Database schema ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
