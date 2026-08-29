"""Generate the bundled synthetic demo scenes (data/sample_videos/)."""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))

from app.core.config import settings          # noqa: E402
from app.utils.sample_video import build_demo_dataset  # noqa: E402


def main() -> int:
    out = settings.sample_videos_dir
    print(f"Generating demo scenes into {out} …")
    data = build_demo_dataset(out)
    for c in data:
        speeds = ", ".join(f"{v['plate']}={v['target_speed_kmh']}km/h" for v in c["expected"])
        print(f"  {c['camera_id']} [{c['environment']}] {c['name']}: {speeds}")
    print(f"Done: {len(data)} clips.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
