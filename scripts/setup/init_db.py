"""Initialise the database schema (idempotent)."""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))

from app.database.session import init_db  # noqa: E402
from app.core.config import settings      # noqa: E402


def ensure_site_pth() -> None:
    try:
        import site
        sp_dirs = site.getsitepackages()
        repo_root = Path(__file__).resolve().parents[2]
        backend_dir = repo_root / "backend"
        yolo_dir = repo_root / "YOLOv11-RGBT-master"
        content = f"{backend_dir.as_posix()}\n{yolo_dir.as_posix()}\n{repo_root.as_posix()}\n"
        for sp in sp_dirs:
            p = Path(sp)
            if p.is_dir() and ("site-packages" in str(p) or p.name == "dist-packages"):
                pth_file = p / "drishti.pth"
                pth_file.write_text(content, encoding="utf-8")
                print(f"[DRISHTI-V] Registered backend path in site-packages: {pth_file}")
    except Exception as exc:
        print(f"[DRISHTI-V] .pth file notice: {exc}")


def main() -> int:
    ensure_site_pth()
    print(f"Initialising database: {settings.database_url}")
    init_db()
    print("Database schema ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

