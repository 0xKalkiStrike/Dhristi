"""Download / verify AI models for DRISHTI-V.

Downloads only what is missing and reports sizes. Heavy models are never pulled
silently — this script is the explicit opt-in.
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def download_yolo(model: str = "yolov8n.pt") -> None:
    print(f"[YOLO] ensuring '{model}' …")
    try:
        from ultralytics import YOLO
        m = YOLO(model)  # ultralytics downloads to its cache if missing
        # locate the weights file
        p = Path(getattr(m, "ckpt_path", "") or model)
        if p.exists():
            print(f"[YOLO] OK: {p} ({human(p.stat().st_size)})")
        else:
            print(f"[YOLO] OK: '{model}' loaded (weights cached by ultralytics)")
    except Exception as exc:
        print(f"[YOLO] WARNING: could not prepare YOLO ({exc}). "
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
    model = sys.argv[1] if len(sys.argv) > 1 else "yolov8n.pt"
    print("=== DRISHTI-V model setup ===")
    check_torch()
    download_yolo(model)
    check_easyocr()
    print("=== done ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
