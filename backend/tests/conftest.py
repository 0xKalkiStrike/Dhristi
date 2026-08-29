"""Pytest fixtures. Uses an isolated SQLite DB so tests never touch dev data."""
import os
from pathlib import Path

# Must be set BEFORE app modules import settings.
_TEST_DB = Path(__file__).resolve().parents[1] / "data" / "test_drishti.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("DETECTOR_BACKEND", "motion")   # tests avoid heavy models
os.environ.setdefault("MONGODB_ENABLED", "false")     # tests don't require a live MongoDB

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _clean_db():
    _TEST_DB.parent.mkdir(parents=True, exist_ok=True)
    for ext in ("", "-wal", "-shm"):
        p = Path(str(_TEST_DB) + ext)
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass
    from app.database.session import init_db
    init_db()
    yield
    from app.database.session import engine
    try:
        engine.dispose()
    except Exception:
        pass



@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c
