"""Download / verify AI models for DRISHTI-V.

Downloads only what is missing and reports sizes. Heavy models are never pulled
silently — this script is the explicit opt-in.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
YOLO11_RGBT_DIR = REPO_ROOT / "YOLOv11-RGBT-master"
sys.path.insert(0, str(BACKEND))
if YOLO11_RGBT_DIR.exists() and str(YOLO11_RGBT_DIR) not in sys.path:
    sys.path.insert(0, str(YOLO11_RGBT_DIR))


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def download_yolo(model: str = "yolo11n.pt") -> None:
    print(f"[YOLOv11] ensuring '{model}' …")
    try:
        from ultralytics import YOLO
        m = YOLO(model)  # ultralytics downloads to its cache if missing
        # locate the weights file
        p = Path(getattr(m, "ckpt_path", "") or model)
        if p.exists():
            print(f"[YOLOv11] OK: {p} ({human(p.stat().st_size)})")
        else:
            print(f"[YOLOv11] OK: '{model}' loaded (weights cached by ultralytics)")
    except Exception as exc:
        print(f"[YOLOv11] WARNING: could not prepare YOLOv11 ({exc}). "
              f"The platform will fall back to torchvision or the classical detector.")


def check_easyocr() -> None:
    print("[OCR] checking EasyOCR …")
    try:
        import easyocr  # noqa: F401
        print("[OCR] EasyOCR available. Recognition models download automatically on first use (~64 MB).")
    except Exception:
        print("[OCR] EasyOCR not installed. Install with: pip install easyocr")


def check_torch() -> None:
    try:
        import torch
        dev = "CUDA" if torch.cuda.is_available() else "CPU"
        print(f"[Torch] {torch.__version__} — runtime: {dev}")
    except Exception:
        print("[Torch] not installed")


def main() -> int:
    model = sys.argv[1] if len(sys.argv) > 1 else "yolo11n.pt"
    print("=== DRISHTI-V model setup (YOLOv11) ===")
    check_torch()
    download_yolo(model)
    check_easyocr()
    print("=== done ===")
    return 0



if __name__ == "__main__":
    raise SystemExit(main())
